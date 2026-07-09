# Claude Code 작업 지시서 — 썸네일 스튜디오 v2 (HTML/CSS + Playwright 렌더러)

## 배경 / 목표
현재 썸네일 렌더링은 `services/thumbnail/canva_branding.py`의 **PIL 기반**(`render_premium_thumbnail`)이라 품질이 낮다. 이를 **HTML/CSS 템플릿 + Playwright 헤드리스 브라우저 렌더링**으로 교체하고, JazzNe 벤치마킹 기반 **6가지 썸네일 형태 시스템**과 **형태별 이미지 생성 프롬프트**를 추가한다.

claude.ai 세션에서 6형태 × 16:9/1:1 디자인을 확정했고, 완성된 참조 구현물 2개가 있다 (아래 "참조 파일" 참고). **디자인 스펙은 이 참조 파일이 정답(source of truth)** 이며, 이번 작업은 그걸 앱 코드로 이식하는 것이다.

먼저 `git log --oneline -5`로 현재 HEAD를 확인하고 시작할 것.

---

## 참조 파일 (대표가 함께 전달 — 반드시 먼저 읽을 것)
1. `seoul_records_thumbnail_studio.html` — 6형태 × 16:9/1:1 인터랙티브 프리뷰. **각 형태의 정확한 레이아웃/폰트/색상/z-index/좌표가 이 안의 CSS·JS에 다 있다.** 이식할 HTML 템플릿의 원본으로 사용.
2. `thumbnail_prompt_builder.py` — 형태별 이미지 생성 프롬프트 빌더. **거의 그대로 앱에 넣으면 된다.**

---

## 작업 1 — 형태별 프롬프트 빌더 통합

`thumbnail_prompt_builder.py`를 `services/thumbnail/form_prompt_builder.py`로 추가한다.

기존 `services/thumbnail/prompt_generator.py`와의 관계:
- 기존 `generate_prompt_batch(country, theme, count, include_person)`는 **형태 개념이 없다**.
- 새 빌더는 `form`(A~F)별 **구도 제약(composition constraints)**을 프롬프트에 강제 주입한다.
- **통합 방식**: `prompt_generator.py`에 `form: str = "A"` 파라미터를 추가하고, form이 주어지면 `form_prompt_builder.build_image_prompt()`의 구도 제약 문자열을 기존 country/theme 프롬프트에 **합성**한다. 기존 호출부 하위호환 유지 (form 없으면 기존 동작).
- **중요**: 기존 `NEGATIVE_PROMPT`가 이미 "no text/letters/watermark…"를 포함하므로, 빌더의 NEGATIVE와 **중복 병합**하되 기존 것을 우선 유지한다. (기존 negative에는 "no VHS/film grain/retro filter"도 있으니 그대로 둘 것 — 최종 VHS는 후처리로 얹기 때문)

form별 피사체 기본값은 빌더에 정의돼 있으나, **country_presets의 문화권별 인물 묘사와 연동**되면 더 좋다:
- A형(인물형)일 때 `include_person=True`인 기존 로직과 겹치므로, A형 = 인물 중앙, 나머지 형태는 각자의 피사체를 쓰도록 정리.
- 최소 구현: form의 composition 제약만 주입해도 동작한다. 문화권 연동은 있으면 좋은 수준.

---

## 작업 2 — HTML/CSS + Playwright 렌더러 (핵심)

### 2-1. 새 모듈 `services/thumbnail/html_renderer.py` 생성

`seoul_records_thumbnail_studio.html`의 각 형태 HTML/CSS를 **서버사이드 템플릿 함수**로 옮긴다. 6형태 × 2비율 = 12개 레이아웃.

함수 시그니처 예시:
```python
def render_thumbnail(
    *,
    form: str,              # "A".."F"
    ratio: str,             # "169" | "11"
    bg_image_path: str,     # 생성/선택된 배경 이미지 (로컬 경로 or file:// URL)
    subject_cutout_path: str | None,  # A형: 배경제거된 인물 PNG (없으면 None)
    kicker: str,            # "CITYPOP PLAYLIST"
    title1: str, title2: str,
    badge: str,             # D형용
    tracks: list[str],      # 트랙리스트
    title_font_css: str,    # 폰트 CSS (기본 Cormorant Garamond)
    kr_font_css: str,       # 한글 폰트
    title_color: str,       # "#f6efe2"
    point_color: str,       # "#e4be6a"
    spine_bg: str = "#1a1420",    # 1:1 A/B형 스파인 배경
    spine_text: str = "#f4efe4",  # 1:1 A/B형 스파인 글씨
    out_path: str,          # 결과 PNG 저장 경로
) -> str:                   # 저장된 PNG 경로 반환
```

**구현 세부 (반드시 지킬 것):**

1. **HTML 조립**: 참조 HTML의 각 형태 CSS/레이아웃을 그대로 사용. 폰트 크기·z-index·좌표(`padding:0 60px`, `font-size:132px` 등)를 참조 파일과 동일하게.

2. **z-index 순서 (A형)**: 배경(0) < 어둡게(1) < 인물컷아웃(2) < **텍스트(5)**. 텍스트가 항상 인물 위. (대표 요청사항)

3. **긴 제목 자동 축소**: 참조의 `fitSplit()` 로직을 이식 — 좌우 분할(A/C/E)에서 제목이 프레임(폭-108px) 넘으면 폰트를 6px씩 줄임(최소 48px).

4. **1:1 스파인**: A·B형만 좌측 스파인(폭 134px, `writing-mode:vertical-rl`, 트랙리스트는 `text-orientation:sideways`로 단어 통째 회전 + flexbox wrap 다열). **주의**: `column-width`(CSS multicol)는 vertical-rl에서 Chromium 버그로 라인이 가로로 눕는다 — 반드시 **flexbox(`flex-direction:row;flex-wrap:wrap`)** 사용. C·D·E·F형은 풀블리드.

5. **1:1 사진 크롭**: A/B형 스파인 있는 경우 `object-position:0% 30%`(좌측 기준) — 인물이 우측이 아닌 좌측에 온전히 보이게. (대표 요청)

6. **Playwright 렌더링 — 필수 안정화 옵션 (이게 없으면 이미지가 안 뜬다)**:
```python
browser = p.chromium.launch(args=["--ignore-certificate-errors"])
context = browser.new_context(ignore_https_errors=True,   # ← 프록시/CDN 인증서 오류 우회. 필수.
                              device_scale_factor=2)        # 2x 고해상도
page = context.new_page()
page.set_viewport_size({"width": W, "height": H})
page.goto(f"file://{html_path}")
# 이미지 로드 완료를 반드시 명시적으로 대기 (43MB급 배경도 있음)
page.wait_for_function("""() => {
    const imgs=[...document.querySelectorAll('img')];
    return imgs.length>0 && imgs.every(i=>i.complete && i.naturalWidth>0);
}""", timeout=30000)
page.wait_for_timeout(400)  # 웹폰트 렌더 안정화
page.screenshot(path=out_path)
```
   - **인증서 무시 + 이미지 로드 완료 대기는 절대 빼지 말 것.** claude.ai 세션에서 이걸 빠뜨려 "텍스트만 있고 배경이 검게 빈" 이미지가 나온 버그를 실제로 겪었다. 원인은 헤드리스 Chromium이 프록시 인증서를 거부(`ERR_CERT_AUTHORITY_INVALID`)한 것.
   - 렌더 후 검증: 결과 PNG를 열어 색상 표준편차가 일정 이상인지(예: stddev > 20) 확인하는 sanity check를 넣으면 좋다. 낮으면 로드 실패로 간주하고 1회 재시도.

7. **이미지 임베드**: 로컬 파일은 `file://` 절대경로 또는 base64로 HTML에 삽입. base64가 로드 실패가 적어 권장(단 대용량 주의, 긴 변 2200px로 리사이즈 후 인코딩).

8. **웹폰트**: Google Fonts를 `<link>`로 로드하되, 오프라인/CDN차단 대비해 폰트 파일을 `assets/fonts/`에 동봉하고 `@font-face`로 로컬 로드하는 방식을 우선 고려. (Playfair Display, Cormorant Garamond, Bodoni Moda, DM Serif Display, Prata, Marcellus, Italiana, Anton, Bebas Neue, Montserrat + 한글 Noto Sans KR, Nanum Myeongjo, Gowun Batang, Song Myung)

### 2-2. 형태별 추천 폰트 매핑
참조 JS의 `FORMS[].recFont`를 그대로 이식:
- A → Cormorant Garamond, B → Playfair Display, C → Bodoni Moda, D → Prata, E → Anton, F → Marcellus.
- 사용자가 폰트를 지정하지 않으면 형태별 추천 폰트를 기본 적용.

---

## 작업 3 — 배경제거 합성 (A형 전용)

A형(인물형)은 **인물을 배경에서 분리해 텍스트 위에 다시 얹는** 레이어 합성이 필요하다.
- 현재 앱에 Adobe/rembg 등 배경제거 수단이 있는지 확인. 없으면 `rembg`(로컬, U2Net) 라이브러리 추가를 검토.
- 파이프라인: 생성된 배경이미지 → 인물 세그멘테이션 → 컷아웃 PNG → `html_renderer`에 `subject_cutout_path`로 전달.
- 인물 bounding box를 알파채널로 측정해서, 텍스트가 인물 얼굴을 피해 배치되도록(또는 최소한 crop 기준점 자동계산) 하면 품질이 올라간다. (claude.ai 세션에서 인물 bbox를 alpha로 측정하는 방식 검증함)
- 배경제거가 어려우면 A형도 우선 "텍스트 최상단 오버레이"만으로 출시하고, 컷아웃 합성은 다음 단계로 미뤄도 된다.

---

## 작업 4 — Thumbnail Studio 탭 UI 확장

`app/tabs/thumbnail_studio.py`의 Prompt Lab / Brand Thumbnail 모드에 다음 추가:
1. **형태 선택** (A~F 6개 버튼 or 라디오) — 선택 시 그 형태 추천 폰트 자동 세팅.
2. **폰트 선택** 드롭다운 (제목 10종 + 한글 4종).
3. **텍스트 입력** (키커/제목1·2/뱃지/트랙리스트).
4. **색상 지정** (제목색/포인트색 + 1:1 A·B형 스파인 배경·글씨색).
5. 형태 선택에 맞춰 **작업 1의 form별 프롬프트가 Prompt Lab에 자동 반영**되게 연결.
6. 미리보기: `html_renderer`로 렌더한 PNG를 `st.image`로 표시.

참조 HTML의 UI/UX(형태 버튼, 실시간 프리뷰, 색상 피커)를 Streamlit으로 옮기는 것이므로, 그 구성을 참고할 것.

---

## 작업 5 — 최종 VHS 후처리 (선택)
대표는 최종 출력에서 VHS는 빼기로 했으나, 옵션으로 남긴다.
- HTML/CSS 레이어로 스캔라인/색수차/그레인을 켜고 끌 수 있게 `vhs: bool = False` 파라미터. 기본 off.

---

## 파일 저장 위치 (기존 alpha.67 구조 준수)
- 썸네일 PNG: `outputs/song_projects/<프로젝트>/thumbnails/`
- 파일명: 기존 `asset_types.py`의 `youtube_thumbnail_16x9.png` / `streaming_cover_1x1.png` 규칙 유지하되, 이전 대화에서 논의한 **프로젝트명 접미사**가 이미 반영됐는지 확인하고 없으면 맞출 것.
- `services/youtube/asset_scanner.py`의 rglob 패턴이 새 파일명을 여전히 잡는지 확인.

---

## 테스트 & 커밋
- `python -m pytest --basetemp=C:\\pytest_tmp -q -p no:cacheprovider` — 기준선 920+ passing 유지.
- `html_renderer`에 대한 단위 테스트 추가: 6형태 × 2비율 렌더가 예외 없이 PNG를 생성하고, 결과 PNG의 색상 stddev가 임계값 이상인지(=이미지 로드 성공) 검증.
- 폰트 자동축소(fitSplit) 로직 테스트: 아주 긴 제목에서 텍스트가 프레임을 안 넘는지.
- 완료 후 origin/main 기준 다음 alpha 버전으로 커밋/푸시.

---

## 우선순위 (한 번에 다 못 하면 이 순서로)
1. **작업 2 (html_renderer)** — 가장 핵심. B형(배경형) 16:9부터 동작시키고 나머지 형태 확장.
2. **작업 1 (form 프롬프트)** — 이미 빌더가 완성돼 있어 통합만 하면 됨.
3. **작업 4 (UI)** — 형태/폰트/색상 컨트롤.
4. **작업 3 (배경제거)** — A형 품질. 어려우면 후순위.
5. **작업 5 (VHS)** — 선택.

각 작업은 독립 커밋으로 나눠서 진행하고, 작업 2를 먼저 끝내 렌더 품질을 확인받은 뒤 나머지로 넘어갈 것.
