# CLAUDE.md — Seoul Records Production OS

이 파일은 Claude(=너)가 이 저장소에서 작업할 때 매 세션 로드되는 프로젝트 컨텍스트다.
앱의 계층 구조, 핵심 서브시스템, 그리고 **대표님(사용자)의 취향·작업 규칙**을 담는다.
여기 적힌 규칙은 기본 동작보다 우선한다.

> 커뮤니케이션: 사용자는 한국어로 말한다. **답변도 한국어로.** 커밋 메시지도 한국어 위주.
> 코드 주석/식별자는 기존 파일의 스타일(영어 위주 + 한국어 UI 문자열)을 따른다.

> **📍 이 레포에서 길 찾기 — 매 세션 처음 온 신입인 너에게.**
> 코드베이스는 **지형(terrain)**, 이 문서는 **지도**다. 미로에서 헤매지 말고 지도부터 봐라.
> 작업 시작 전 오리엔테이션 순서: **① §0 작업 철학 → ② §2 아키텍처(=지형 지도) →
> ③ `AGENTS.md`(실전 함정/노하우) → ④ §5 "자주 건드리는 파일" 표에서 목적지 찾기.**
> 어디를 고칠지 모르겠으면 추측하지 말고 §2 지도로 돌아오거나 §4처럼 grep으로 좌표를 찍어라.

---

## 0. 작업 철학 (먼저 읽어라 · 최우선)

이 4가지는 다른 어떤 규칙보다 앞선다. 매 작업의 사고 방식이다.
(출처: Andrej Karpathy의 LLM 코딩 함정 관찰. 전문: `.claude/skills/karpathy-guidelines/SKILL.md`.)

1. **코딩 전에 먼저 생각해라.** — 추측하지 말고, 혼란을 숨기지 말고, 트레이드오프를 드러내라.
   가정은 명시한다. 해석이 여러 개면 조용히 하나 고르지 말고 제시한다. 더 단순한 길이 있으면
   말한다(근거 있으면 pushback). 막히면 멈추고 **뭐가 불분명한지 이름 붙여** 묻는다.
2. **단순함이 우선이다.** — 문제를 푸는 **최소 코드**. 투기적인 것 금지. 요청 안 한 기능·유연성·
   설정·불가능한 시나리오의 방어코드·단일사용 추상화 금지. 200줄이 50줄이면 다시 써라.
   자문: "시니어가 이거 과설계라 할까?" → 그렇다면 단순화.
3. **외과적인 수정.** — 꼭 필요한 것만 건드리고, 내가 만든 것만 치운다. 인접 코드/주석/포맷을
   "개선"하지 말고, 안 깨진 걸 리팩터하지 마라. 무관한 dead code는 **삭제 말고 언급만.** 내 변경이
   만든 orphan(안 쓰는 import/변수/함수)만 정리. **테스트: 바뀐 모든 줄이 요청에서 직접 유래하나?**
4. **목표중심의 실행.** — **성공 기준을 정의하고, 검증될 때까지 루프.** 명령을 검증가능 목표로
   변환: "검증 추가"→"잘못된 입력 테스트 작성 후 통과", "버그 수정"→"재현 테스트 작성 후 통과".
   멀티스텝은 계획을 명시(`1.[단계]→검증:[확인] / 2.…`). "된 것 같다"가 아니라 "검증됐다"일 때만
   완료 보고. 검증 못 한 부분은 정직하게 명시. (강한 성공기준이 있어야 스스로 루프할 수 있다.)

---

## 1. 앱이 뭐냐

**AI 음악 레이블 프로덕션 OS.** 한국형 **시티팝(city pop)** 플레이리스트를 만들어 YouTube에
올리는 1인 레이블(Seoul Records)의 전 파이프라인을 자동화한다. Streamlit 웹앱(로컬/LAN)이 주
인터페이스. `frontend/`에 Next.js 콘솔도 있으나 현재 주력은 Streamlit(`app/main.py`).

파이프라인(= 좌측 내비 순서, `app/main.py`의 NAV):

```
🎵 Song Lab       곡 생성 (Suno) — Quick Single / Auto Batch / 프로젝트 관리 / Manual Import
🖼️ Thumbnail Studio 썸네일/앨범자켓 생성 (AI 이미지 + HTML 렌더 텍스트 오버레이)
🎬 Video Renderer  MP3 → 목표길이 플레이리스트 영상(ffmpeg, 오디오 반응형 비주얼라이저)
▶️ YouTube Package YouTube 업로드 패키지(제목/설명/태그/챕터) + API 업로드(private 기본)
✅ Production QA    산출물 검수
🎶 UnitedMasters   유통용 패키지
📜 History / 📚 Library / 📁 프로젝트 관리 / ⚙️ Settings
```

버전은 `v1.0.0-alpha.N`. **기능 하나 = alpha 커밋 하나**로 계속 올라간다(현재 alpha.99+).

---

## 2. 계층 구조 (아키텍처)

4개 레이어로 나뉜다. 위에서 아래로 의존한다.

```
app/            ── UI 레이어 (Streamlit). 얇게 유지, 로직은 services로.
  main.py         진입점 + 내비 + 전역 CSS(모바일 @media 포함)
  tabs/           탭별 렌더 함수 (song_lab.py, thumbnail_studio.py, video_renderer.py,
                  youtube_package.py, production_qa_tab.py, unitedmasters_tab.py, …)
  ui/             재사용 UI 조각 (song_card.py, live_console.py)
  project_manager.py  곡 프로젝트 CRUD (song_projects/ 폴더), find_song_file 등
  dashboard.py, config.py, state_machine.py, orchestrator.py

services/       ── 비즈니스 로직 레이어 (UI 없음, 테스트 가능)
  thumbnail/      프롬프트 생성/합성, 이미지 provider, 세션 스토어, HTML 렌더, 브랜딩, export
  youtube/        메타데이터/SEO 설명 생성, 번역, 챕터, OAuth, 업로드, 자산 스캔
  video/          플레이리스트 플랜, 렌더 플랜(ffmpeg), 비주얼라이저, 오버레이
  production/     QA 스캐너/체크리스트
  unitedmasters/  유통 패키지
  job_store.py + *_job_manager.py   백그라운드 잡 큐(공통)
  suno_auto_download.py, suno_cleanup.py   Suno 다운로드/정리
  shared_mood.py  곡·썸네일·YouTube가 공유하는 무드
  library_labels.py  라이브러리 공통 라벨/트랙 메타

providers/      ── 외부 연동 레이어 (교체 가능한 provider 패턴, mock 항상 존재)
  ai/base.py      작사/스타일 LLM (OpenAI/Gemini/Mock) + SONG_MOODS + 시스템프롬프트
  ai/languages.py 언어별(한/일/태/베/인니) 가사·도시 설정
  image/          이미지 생성 (nano_banana, mock, local_upload)
  suno/           곡 생성 (suno_cli_provider 실사용, mock/manual_import/web 등)
  design/         Canva/Pillow 오버레이
  upload/         YouTube 업로드

workers/        ── 백그라운드 detached 프로세스 (subprocess.Popen, DETACHED)
  suno_generation_worker.py, thumbnail_generation_worker.py,
  video_render_worker.py, youtube_upload_worker.py, studio_supervisor_worker.py

tests/          ── pytest. 기능마다 test_*_vNNN.py. 현재 1090+ 통과.
```

### 핵심 서브시스템 메모
- **백그라운드 잡 큐**: `services/job_store.py`(create_job/update_job/list_jobs/get_active_jobs,
  mode별) + `*_job_manager.py`(detached worker 기동) + `workers/*`. 무거운 생성(곡/썸네일/영상)은
  UI 스레드를 막지 않게 별도 프로세스로. 한 번에 하나만 running, 나머지는 queued→자동 chain.
  Thumbnail: `job["project"]`=session_id. `app/ui/live_console.py`가 진행률/큐 패널 렌더.
- **이미지 provider 팩토리**: `services/thumbnail/image_provider.get_image_provider(use_real, model,
  engine)`. engine: `gemini`(기본) / `apiframe_nanobanana`(Nano Banana 2, 프롬프트 2000자 제한) /
  `gpt_image` / `midjourney_linkr`(LinkrAPI, 그리드 4장 분할). 계약:
  `generate(prompt, out_path, negative_prompt, index, meta, aspect, ref_image_path) -> dict`.
- **썸네일 프롬프트**: `prompt_generator.py`(템플릿: 국가 preset + scene/camera/mood + FORM_SPECS
  A~F + **THUMB_ART_STYLES**) / `prompt_composer.py`(한글 자유서술 → 영어 프롬프트, OpenAI→Gemini).
  하나의 이미지에서 16:9 썸네일 + 1:1 커버를 파생.
- **무드 시스템**: 곡 무드 `providers/ai/base.SONG_MOODS`(refreshing/wistful/calm/romantic/dreamy),
  썸네일 아트스타일 `THUMB_ART_STYLES`(anime/photo/analog), 셋을 `shared_mood`로 연결.
- **Suno 다운로드**: 곡당 클립 2개 생성 → `suno_auto_download.auto_download_final_version`가
  승자 1개만 받고 나머지는 `delete_clips`로 Suno에서 삭제(기본 ON, 길이 tie여도 삭제).
- **YouTube 설명**: `services/youtube/seo_description.py`가 기본 포맷(인트로·감성키워드·추천무드·
  총 N곡·트랙리스트·FAQ·저작권·해시태그)을 골격으로, 가변 카피만 OpenAI→Gemini로 SEO 생성.
  트랙리스트는 실제 업로드 음원(chapters)에서 그대로. **DJ HANA 페르소나는 제거됨.**

---

## 3. 대표님 취향 / 창작 방향 (중요 — 생성물 품질 기준)

이건 지금까지 수십 번의 피드백으로 확립된 미감이다. 생성 프롬프트/카피를 만들 때 반드시 반영.

### 음악 (시티팝)
- **밝고 청량하면서도 nostalgic한 시티팝.** 엔카/트로트/뽕짝 절대 금지. 항상 세련된
  1980~90s 일본 시티팝 사운드(장르), 가사 언어만 바뀜.
- 무드는 **고정이 아니라 선택**: 청량/쓸쓸/잔잔/설렘/몽환. 어둡고 무겁게만 가지 말 것.
- 색소폰 금지, 과한 드럼필/벨팅 금지(→ 트로트로 샘). 저음 여성 보컬 위주지만 배치 다양화.

### 썸네일 / 비주얼
- **유튜브 tokyo citypop 조회수 상위 다수가 1980-90s 시티팝 애니 일러스트** → 아트스타일
  기본값 = **anime**(나가이 히로시/스즈키 에이진 앨범아트 느낌). photo·analog도 선택 가능.
- 인물: 20대 초반 여성, **감성적이고 세련된 시티팝** 무드. **과한 레트로/촌스러운 코스튬 금지**,
  화려한 오프숄더 클리셰 금지. 착장 다양화(니트/블레이저/트렌치/데님/새틴 등).
- 배경: 자연스러운 네온 간판 + 살짝 블러된 행인으로 도시의 생동감(과하지 않게).
- 제목 텍스트 자리(세이프 밴드)를 인물/얼굴 위에 겹치지 말 것.

### YouTube 카피
- **센스있고 자연스럽게, 촌스럽지 않게, AI 티 안 나게.** 클릭베이트/느낌표 남발 금지.
- 무드(예: "비 내리는 서울밤")를 **제목·설명 전체가 반영**하도록. 태그는 광범위 영어 SEO 세트 유지.
- 저작권 문구: "제작자가 AI 도구로 만든 오리지널 창작물, 무단 복제/재업로드/2차가공 금지" 유지.

### UX
- **모바일 최우선.** 폰트 안 짤리게 줄바꿈, 큰 탭 타겟, 컴팩트한 목록, 셀렉트박스 안 짤림.
- 한국어 UI. 위험한 동작(프로젝트/곡 삭제 등)은 **2단계 확인**.

---

## 4. 작업 규칙 (워크플로우)

1. **앱 재실행은 항상**:
   `streamlit run app/main.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true`
   (LAN/외부 접속 필요. PowerShell로 기존 프로세스 kill 후 재기동. 실제 프로세스는 detached라
   background 작업 추적이 killed 떠도 포트 8501이 살아있으면 정상.)
2. **테스트**: `python -m pytest --basetemp=/c/pytest_tmp_XXX -q -p no:cacheprovider`.
   기능 완료 = **전체 스위트 그린** 확인 후 커밋. 기능마다 `tests/test_*_vNNN.py` 추가.
3. **커밋 케이던스**: 기능 하나 = `v1.0.0-alpha.N: <한국어 요약>` 커밋 1개 → push → 앱 재시작.
   커밋 바디에 무엇을/왜/테스트 결과를 한국어로.
4. **보안(엄수)**: API 키는 **환경변수로만**. 절대 코드에 하드코딩하지 말고, 로그에도 남기지 말 것.
   방화벽/라우터/시스템 보안 설정 변경 금지.
5. **정직하게 보고**: 테스트 실패면 실패라고, 스킵했으면 스킵했다고. 실물 확인이 필요한 부분은 명시.
6. **환경**: Windows 11 / PowerShell(주) + Bash 툴 / `.venv`. 임시파일은 스크래치패드 디렉토리에.
   포트 8501을 OneDrive 복사본 인스턴스가 잡는 사고 주의(그 사본으로 실행하지 말 것).

### Quick Start (copy-paste)
```bash
# 설치 (최초 1회)
python -m venv .venv && source .venv/Scripts/activate && pip install -r requirements.txt
# 실행 (항상 이 옵션으로 — LAN/외부 접속)
source .venv/Scripts/activate && streamlit run app/main.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true
# 테스트 (전체)
python -m pytest --basetemp=/c/pytest_tmp_run -q -p no:cacheprovider
```

### 주요 환경변수 (전부 env 전용 · 코드 하드코딩 금지)
- `OPENAI_API_KEY`, `GOOGLE_GEMINI_API_KEY` — 작사/스타일, 썸네일 프롬프트 합성, YouTube SEO 설명·번역, Gemini 이미지. **둘 중 하나라도 있어야 LLM 경로 동작**(없으면 템플릿 폴백).
- `LINKRAPI_API_KEY` — 썸네일 Midjourney(LinkrAPI) 엔진. `SEOUL_IMAGE_BACKEND`/`SEOUL_IMAGE_MODEL` — 이미지 엔진/모델 오버라이드.
- `SUNO_COOKIE` / `SUNO_CLI_BIN` — 곡 생성(suno-cli). YouTube 업로드는 OAuth(토큰은 `services/youtube/token_store`).
- 그 외 `SEOUL_MJ_*`/`SEOUL_NANOBANANA_TIMEOUT`/`SEOUL_GPTIMAGE_*` 등 provider 타임아웃·재시도 튜닝(선택).

---

## 5. 자주 건드리는 파일 (빠른 참조)

| 하고 싶은 것 | 파일 |
|---|---|
| 곡 스타일/작사 프롬프트, 무드 | `providers/ai/base.py` (SONG_MOODS, _STYLE_GUIDANCE, build_system_prompt) |
| 썸네일 이미지 프롬프트 | `services/thumbnail/prompt_generator.py` (THUMB_ART_STYLES, FORM_SPECS, _portrait/_background) |
| 한글→영어 썸네일 프롬프트 | `services/thumbnail/prompt_composer.py` |
| 썸네일 텍스트 오버레이/폼 | `services/thumbnail/html_renderer.py`, `form_prompt_builder.py` |
| Song Lab UI (Quick/Auto Batch/프로젝트) | `app/tabs/song_lab.py` |
| 썸네일 스튜디오 UI | `app/tabs/thumbnail_studio.py` |
| 영상 렌더/플레이리스트 | `services/video/*`, `app/tabs/video_renderer.py` |
| YouTube 제목/설명/태그/SEO | `services/youtube/seo_description.py`, `metadata_generator.py` |
| YouTube 패키지 UI | `app/tabs/youtube_package.py` |
| 백그라운드 잡 | `services/job_store.py`, `services/*_job_manager.py`, `workers/*` |
| 곡 다운로드/Suno 정리 | `services/suno_auto_download.py`, `services/suno_cleanup.py` |
| 모바일 CSS | `app/main.py` (`@media (max-width:640px)` 블록) |

---

_이 문서는 살아있는 컨텍스트다. 큰 구조 변경이나 새 취향/규칙이 확정되면 여기도 갱신할 것._
