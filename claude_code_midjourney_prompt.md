# Claude Code 작업 지시서 — Midjourney(LinkrAPI) 이미지 provider 추가

## 목표
현재 썸네일 배경 이미지 생성은 Gemini(Nano Banana)와 OpenAI(GPT-Image) 두 provider가
`services/thumbnail/image_provider.py`의 `ImageGenProvider` 인터페이스 뒤에 붙어 있다.
여기에 **세 번째 provider로 Midjourney(LinkrAPI 프록시)**를 같은 패턴으로 추가한다.

시작 전 `git log --oneline -3`으로 현재 HEAD(alpha.72 이후)를 확인할 것.

## 기존 구조 (이미 파악됨 — 이 패턴을 그대로 따를 것)
- `services/thumbnail/image_provider.py`
  - `class ImageGenProvider` — 추상. 핵심 메서드: `generate(self, prompt, out_path,
    negative_prompt="", index=0, meta=None, aspect="16:9", ...)`. **out_path에 실제 이미지
    파일을 써서 경로를 반환**하는 게 계약.
  - 구현체: `MockImageGenProvider`, `GeminiRestImageProvider`, `GeminiImageProvider`
  - `get_image_provider(use_real, model, ...)` 팩토리가 provider를 선택.
    (use_real=False거나 키 없으면 Mock으로 폴백. **테스트는 절대 실제 provider 안 씀.**)
- `services/thumbnail/openai_image_provider.py`
  - `class OpenAIGptImageProvider(ImageGenProvider)` — 동일 인터페이스로 GPT-Image 구현.
- API 키는 **환경변수**로 읽는다 (예: GOOGLE_GEMINI_API_KEY). 사이드바 크리덴셜 입력이
  환경변수로 들어가 자동으로 잡히는 구조. 미드저니도 이 방식을 따를 것.

---

## LinkrAPI 스펙 (확인된 사실)
- 인증: `lkr_xxx` 형태 API 키. `Authorization: Bearer lkr_xxx` 헤더로 추정
  (문서에서 정확한 헤더명 확인 — Bearer가 아니면 그에 맞게. 아래 "미확인" 참고).
- **비동기 흐름**:
  1. `POST /v1/imagine` — body에 `prompt` (+ webhook_url 선택). 즉시 `task_id` 반환.
  2. `GET /v1/fetch/{task_id}` — 폴링. status가 completed면 image_url + actions(U1~U4,
     V1~V4, Reroll) 반환. **우리는 webhook 안 씀(로컬 앱, 공개 URL 없음) → 폴링만.**
  3. imagine 결과는 **2×2 그리드 4장**. 최종 1장을 얻으려면 **upscale** 액션(U1~U4) 실행:
     또 하나의 비동기 task → 다시 fetch 폴링 → upscale된 단일 이미지 URL.
  4. 그 URL의 이미지를 다운로드해 out_path에 저장.

⚠️ **미확인(문서에서 반드시 확인할 것)** — 코드 짜기 전에 LinkrAPI 대시보드/문서에서 확정:
  a. 정확한 인증 헤더 형식 (Authorization: Bearer? x-api-key? )
  b. base URL (https://api.linkrapi.com? https://linkrapi.com/api? )
  c. imagine 요청 body 필드명 (prompt 외에 aspect ratio를 어떻게 넘기는지 —
     보통 프롬프트 안에 `--ar 16:9`로 넣음. Midjourney는 파라미터를 프롬프트 텍스트에
     붙이는 방식이 표준.)
  d. upscale(U1) 액션을 트리거하는 엔드포인트/파라미터 형식
     (예: POST /v1/action {task_id, action:"U1"} 같은 형태일 것)
  e. fetch 응답의 status 값 종류 (pending/processing/completed/failed 등)와
     완료 시 image_url이 담기는 정확한 JSON 경로.
  이 5개를 확인 못 하면, 확인 가능한 부분까지만 구현하고 미확인 지점을 TODO로 표시한 뒤
  나한테 물어볼 것. (LinkrAPI 문서 URL을 내가 줄 수 있음.)

---

## 작업 1 — MidjourneyProvider 신규

`services/thumbnail/midjourney_provider.py` 생성:
- `class MidjourneyProvider(ImageGenProvider)` — 기존 인터페이스 100% 준수.
  `generate(self, prompt, out_path, negative_prompt="", index=0, meta=None, aspect="16:9", ...)`
- generate() 내부에서 **동기적으로 전 과정 처리**(겉보기엔 다른 provider와 동일하게 동작):
  1. aspect를 Midjourney 파라미터로 변환해 프롬프트 끝에 append:
     "16:9"→` --ar 16:9`, "1:1"→` --ar 1:1`, "9:16"→` --ar 9:16`.
     negative_prompt가 있으면 ` --no <neg>` 형태로 변환(Midjourney 문법).
  2. POST /v1/imagine → task_id.
  3. GET /v1/fetch 폴링 (지수 backoff 또는 고정 간격, 예: 5초 간격, 최대 ~5분 타임아웃).
     Midjourney는 느리다 — 타임아웃을 넉넉히(5분) 잡되, 상한을 두고 실패 처리.
  4. 완료된 그리드에서 **U1(좌상단) upscale 실행** (index를 활용해 U1~U4 중 선택 가능하게
     하되 기본 U1). → 다시 fetch 폴링.
  5. upscale된 단일 image_url 다운로드 → out_path에 저장 → out_path 반환.
- API 키: 환경변수 `LINKRAPI_API_KEY`(우선) 에서 읽기. 없으면 명확한 예외.
  ⚠️ **키를 로그에 절대 남기지 말 것** (기존 provider들이 지키는 규칙과 동일).
- 네트워크/타임아웃/실패 시 깔끔한 예외 + 부분 결과 정리(임시파일 삭제).
- **requests만 사용**(기존 GeminiRest처럼 SDK 불필요). 추가 의존성 없이.

## 작업 2 — 팩토리 & 선택 로직 통합

`get_image_provider()`(image_provider.py)에 midjourney 선택지 추가:
- provider 종류를 문자열로 고를 수 있게: 예) `get_image_provider(use_real=True,
  provider="midjourney"|"gemini"|"openai")`. 기존 호출 시그니처 **하위호환 유지**
  (provider 인자 없으면 지금과 동일하게 gemini 기본).
- midjourney 선택 시 `LINKRAPI_API_KEY`가 있으면 MidjourneyProvider, 없으면 Mock 폴백.
- **테스트는 절대 실제 LinkrAPI를 호출하지 않도록** 기본 use_real=False 유지.

## 작업 3 — UI에 provider 선택 추가

`app/tabs/thumbnail_studio.py`(또는 이미지 생성 트리거하는 실제 탭)에서:
- 이미지 생성 provider를 고르는 셀렉트박스 추가: "Gemini (Nano Banana)" / "GPT-Image" /
  "Midjourney (LinkrAPI)". 기존 기본값은 유지(회귀 방지).
- Midjourney 선택 시 안내: "미드저니는 생성에 1~3분 걸릴 수 있습니다" (비동기라 느림).
- 사이드바 크리덴셜 입력에 LinkrAPI API 키 필드 추가 → 환경변수 LINKRAPI_API_KEY로 주입.
  (기존 Gemini/OpenAI 키 입력과 같은 방식으로.)
- 진행 중 상태 표시(st.spinner 또는 폴링 진행률) — 오래 걸리니 사용자에게 피드백 필수.

## 작업 4 — 형태별 프롬프트 빌더와 연동

이미 있는 `form_prompt_builder.py`(형태 A~F별 구도 제약 프롬프트)는 provider 중립적이다.
Midjourney에도 그대로 쓰되, **Midjourney 특화 접미사**만 추가 고려:
- Midjourney는 `--ar`, `--style raw`, `--stylize`, `--no` 등 파라미터를 프롬프트에 붙인다.
- 인수인계 메모리의 MV 프롬프트 규칙(예: `--ar 16:9 --style raw --stylize 110~140`)이
  시티팝 무드에 맞으니, Midjourney provider일 때 이런 파라미터를 옵션으로 붙일 수 있게.
- 단 negative는 `--no`로, aspect는 `--ar`로 (작업 1에서 처리). 텍스트 프롬프트 본문은
  form_prompt_builder 것을 재사용. **"no text/letters/watermark"는 Midjourney에선
  `--no text, letters, watermark, logo`로 변환.**

## 테스트 & 커밋
- MidjourneyProvider 단위 테스트: **실제 API 호출 금지**. `requests`를 mock(responses
  라이브러리 또는 unittest.mock)해서 imagine→fetch→upscale→download 흐름을 검증.
  - task_id 파싱, 폴링 완료 감지, upscale 트리거, 이미지 저장까지 mock으로 커버.
  - 타임아웃/실패 경로도 테스트.
- 팩토리 테스트: provider="midjourney"인데 키 없으면 Mock 폴백하는지.
- 기존 테스트 987 passing 유지.
- `python -m pytest --basetemp=C:\pytest_tmp -q -p no:cacheprovider`
- 커밋 분리: (1) MidjourneyProvider + 팩토리, (2) UI + 크리덴셜, (3) 프롬프트 연동.
  각 독립 커밋, origin/main 기준 다음 alpha로 푸시.

## 진행 방식
먼저 "미확인 5개(a~e)"를 LinkrAPI 문서에서 확인한 결과와, 구현 계획을 요약해서 보여줘.
문서 접근이 안 되면 나한테 문서 URL이나 대시보드 정보를 요청해. 내 확인 후 코딩 시작.
절대 내 API 키를 코드에 하드코딩하지 말고 환경변수로만 처리할 것.
