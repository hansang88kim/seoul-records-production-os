# AGENTS.md — Claude를 위한 실전 노하우 (이 저장소 전용)

미래의 나에게. 이건 이 저장소에서 실제로 삽질하며 얻은 것들이다. 매번 다시 배우지 말고
여기부터 읽어라. **토큰·시간 절약 + 완성도**가 목적. (프로젝트 구조·취향은 `CLAUDE.md` 참고.)

---

## 0. 매 작업의 기본 루프 (검증된 순서)

1. 요청 파악 → **애매하면 만들기 전에 물어라**(§5). 기존 기능일 수 있으니 **먼저 grep**(§4).
2. 코드 수정.
3. **타겟 테스트만** 먼저 (`pytest tests/test_touched_*.py`) — 빠르게 회귀 확인.
4. 통과하면 **전체 스위트 1회** (`--basetemp=/c/pytest_tmp_XXX`, ~2–4분). 그린 확인.
5. `git add <파일들>` → `alpha.N` 커밋(한국어) → push.
6. **앱 재시작**(§1) → 포트 8501 살아있는지 확인 → 사용자에게 한국어로 간결 보고.

전체 스위트는 느리다. **반복해서 돌리지 마라.** 커밋 직전 딱 1번.

---

## 1. 환경 함정 (Windows / PowerShell / Streamlit)

- **cp949 인코딩 폭탄**: Python에서 한글·이모지를 `print()`하면
  `UnicodeEncodeError: 'cp949' codec can't encode`. 스모크 테스트할 때 매번 터진다.
  → 앞에 `PYTHONIOENCODING=utf-8` 붙이거나 `sys.stdout.buffer.write(s.encode('utf-8'))`.
- **Streamlit 재시작 = detached 프로세스**:
  `cd ... && source .venv/Scripts/activate && exec streamlit run app/main.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true`
  를 Bash `run_in_background`로 띄운다. **나중에 background task가 `killed`/`exit 127`로 떠도
  당황하지 마라** — 그건 추적 래퍼가 죽은 것이고, 실제 Streamlit은 detached라 계속 산다.
  진짜 상태는 **포트로 확인**: `Get-NetTCPConnection -State Listen -LocalPort 8501`.
- **재시작 절차**: PowerShell로 기존 `streamlit run app/main.py` 프로세스 kill →
  `Start-Sleep 2` → 포트 free 확인 → 새로 기동 → `sleep 8` 후 output에서 `Local URL` grep.
- **OneDrive 유령 인스턴스**: `C:\Users\hansa\OneDrive\...` 복사본이 포트 8501을 잡아 옛 코드가
  뜨는 사고가 있었다. 그 사본으로 실행하지 말 것. 이상하면 모든 streamlit 프로세스 kill.
- **pytest basetemp**: 항상 `--basetemp=/c/pytest_tmp_XXX -q -p no:cacheprovider`. 매번 다른
  이름 쓰고 끝나면 `rm -rf`. 안 그러면 "directory not empty" 충돌.
- **큰 문자열 치환**: 거대한 파일에서 함수 하나 통째로 지울 땐 Edit보다
  `python - <<'PY' ... 인덱스 슬라이싱 ... PY`가 안전했다(예: DJ HANA 함수 제거).
- **커밋 CRLF 경고**(`LF will be replaced by CRLF`)는 에러 아님 — 무시.
- **멀티라인 한국어 커밋**: Bash에서 `git commit -q -m "$(cat <<'EOF' ... EOF)"`.

---

## 2. Streamlit 특유 패턴 (모르면 버그)

- **버튼이 다른 위젯 값 못 씀 (staging-key)**: 🎲 같은 버튼은, 이미 렌더된 text_input의 key를
  직접 못 바꾼다. → 버튼은 `st.session_state["X_pending"] = 값` 만 하고 `st.rerun()`.
  위젯 렌더 **전에** `if "X_pending" in ss: ss["X"] = ss.pop("X_pending")`로 옮긴다.
  (concept 🎲, mood 🎲 둘 다 이 패턴.)
- **selectbox `format_func`은 표시용**: 반환값은 여전히 옵션 **값**(라벨 아님). 그래서 라벨에
  곡 수/태그 붙여도 반환·다운스트림 안 깨진다. 안심하고 라벨 꾸며라.
- **rerun이 실행 중 스크립트를 중단**: 동기 생성 도중 사용자가 다른 걸 누르면 끊긴다. 그래서
  무거운 생성(곡/썸네일/영상)은 전부 **detached worker + 잡 큐**로 돈다(`services/job_store.py`
  + `*_job_manager.py` + `workers/*`). 새 무거운 기능도 이 패턴을 따라라, 동기로 하지 마라.
- **`st.container(key=...)`** → `st-key-<key>` CSS 클래스 생성. 모바일 CSS 예외 처리에 활용.
- **모바일 CSS**는 `app/main.py`의 한 덩어리 `<style>` 안 `@media (max-width:640px)` 블록.
  컬럼 스택/줄바꿈/탭 타겟 크기 여기서. 수정 후 `style.count('{')==style.count('}')`로 밸런스 확인.

---

## 3. 프롬프트/LLM 문자열 수정 (테스트가 잘 깨지는 지점)

- **공유 프롬프트 문자열 고치기 전에 테스트부터 grep**: 테스트가 특정 부분문자열을 assert한다.
  예) `_STYLE_GUIDANCE`, `build_system_prompt`, `_portrait_prompt`("album cover" 등),
  `_build_llm_instruction`("lens","lighting","color palette","professional","60-110 words").
- **국적 오염 주의**: 아트스타일 렌더 문구에 "Japanese"를 넣었더니 **태국 프롬프트에 "Japanese"가
  새어** 테스트(`"Japanese" not in th`) 깨짐. 장르는 "city pop"만으로 충분, 국적 단어 빼라.
- **부분문자열 assert는 취약**: 애니 프롬프트가 "NOT photorealistic"라 `"photorealistic" not in`
  이 실패했다(내 테스트 실수). → 정확한 문구(`"NOT photorealistic" in`)를 assert.
- **Apiframe(Nano Banana) 프롬프트 2000자 제한**: `_fit_prompt`가 negative를 먼저 자르니 **main이
  2000 넘으면 안 된다.** 프롬프트에 문장 추가하면 `generate_flow_prompt(...)['main_prompt']` 길이
  확인. 넘으면 boilerplate 압축. (form-A 케이스가 제일 길다.)
- **새 파라미터 스레딩**: mood/art_style처럼 여러 호출부에 새 인자 넣을 땐 **default 값을 줘서**
  기존 호출부·테스트가 안 깨지게. 프로바이더 시그니처 3개(OpenAI/Gemini/Mock) 다 바꾸기 싫으면
  **concept/문자열에 baking**하는 편법도 고려(단, 시스템프롬프트가 그걸 덮어쓰지 않게 가이드 완화).
- **LLM 호출 재사용**: OpenAI→Gemini 폴백 호출기가 `services/youtube/description_translator.py`에
  (`_call_openai`, `_call_gemini`) 이미 있다. 새로 만들지 말고 재사용. **키는 env 전용, 미로깅.**
  키 없을 때 항상 **템플릿 폴백** 경로를 둬라(테스트는 키가 없으니 폴백 경로가 실행됨).

---

## 4. "새 기능"인 줄 알았는데 이미 있던 것들 (먼저 grep!)

만들기 전에 `grep -rn "def <동사>" services/ app/` 부터. 실제로 이미 있던 것들:
- **프로젝트 삭제**: `project_manager.delete_song_project` 이미 존재(UI만 없었음).
- **곡 다운로드 1개 + 나머지 Suno 삭제**: `suno_auto_download.auto_download_final_version(
  delete_other=True)` 이미 기본 ON이었음(tie일 때만 안 지우던 것만 고침).
- **타임스탬프 트랙리스트**: `video/playlist_builder.build_playlist_plan` + `format_chapters_txt`가
  이미 그 포맷(⏱ Tracklist, 반복 N) 생성. 재사용하면 끝.
- **HTML 텍스트 오버레이 폼**: `services/thumbnail/html_renderer.py`, `services/thumbnail/form_prompt_builder.py`(FORM_SPECS).
→ 교훈: **grep 30초가 구현 30분을 아낀다.** 특히 "추가해줘" 요청은 이미 있을 확률 높음.

---

## 5. 요청 해석 (엉뚱한 거 만들어서 낭비한 사례)

- **"YouTube 패키지에 MP3/WAV 업로드"** → 나는 처음에 "최종 영상칸에 파일 업로드"로 이해했는데,
  실제 의도는 **"MP3 올리면 타임스탬프 트랙리스트 자동 생성"**이었다. 사용자가 스크린샷으로
  바로잡음. → **의도가 애매하면(기본값 문제가 아니라 "무엇을 만들지"가 갈리면) 만들기 전에
  AskUserQuestion.** 그리고 옵션보다 **구체적 예시/스크린샷**이 의도를 훨씬 정확히 드러낸다.
- AskUserQuestion을 써도 내 옵션이 사용자의 진짜 의도를 못 담을 수 있다. 답이 와도 결과가 좀
  이상하면 한 번 더 확인.
- 반대로, 관례적 기본값이 있는 사소한 선택은 **묻지 말고** 합리적 기본으로 진행하고 알리기만.

---

## 6. 서브시스템 제거/대규모 리팩터 (숨은 커플링 조심)

- **DJ HANA 제거**(49개 참조, 테스트 4파일): `app/ services/ tests/` 전부 grep. **문자열 상수/
  마커까지** 확인해야 한다 — `description_translator._TRACKLIST_MARKER`가 "…DJ HANA Mixset…"라서
  설명 포맷 바꾸니 번역의 트랙리스트 분리가 조용히 깨졌다.
- 삭제 전에 **호출부부터 새 함수로 교체** → 그 다음 옛 함수 제거(역순이면 import 에러 연쇄).
- 파라미터 이름 변경(`use_djhana_template`→`use_seo_template`)은 테스트에도 있으니 같이 갱신.

---

## 7. 세션 상태(session_state) 함정

- **백그라운드 잡의 세션 드리프트**: 썸네일을 여러 개 큐에 넣으면 `thumb_session_id`가 아직 대기
  중인 세션을 가리켜 결과가 "0/0"로 보였다. 표시용 폴백은 **로컬 변수로만** 하고 `thumb_session_id`
  자체를 바꾸지 마라(바꿨더니 프리미엄/Exports 모드가 "세션 있음"으로 오인해 다른 테스트가 깨짐).
  폴백은 "이번 UI에서 생성함(=thumb_prompts 있음)"일 때로 **조건을 좁혀라.**

---

## 8. 하지 말 것 / 지킬 것

- API 키 하드코딩·로깅 **금지**(env 전용). 방화벽/보안 설정 변경 **금지**.
- 위험 동작(프로젝트/곡 삭제)은 **2단계 확인** UI로.
- 테스트 실패를 감추지 마라. 실물 확인이 필요한 부분(실제 LLM/이미지 생성)은 "키 있어야 함" 명시.
- 커밋은 **기능 하나 = alpha 하나**. 커밋 바디에 무엇/왜/테스트 결과(한국어).

---

_새로 삽질해서 배운 게 생기면 여기 한 줄씩 추가해라. 이 파일이 두꺼워질수록 다음 세션이 빨라진다._
