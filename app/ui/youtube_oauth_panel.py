"""
app/ui/youtube_oauth_panel.py — shared YouTube OAuth account panel.

v1.0.0-alpha.51: previously this UI was inlined only inside
app/tabs/youtube_package.py, and the client_secret.json file_uploader was
ALWAYS rendered empty (Streamlit widgets don't remember a previously
picked file across reruns/page navigation) even though the secret was
already saved permanently to outputs/youtube_auth/client_secret.json. That
made it look like the user had to re-upload it every time they opened the
tab, when in fact the backend never needed a second upload.

This panel is now:
  * PERSISTED-AWARE — once ts.has_client_secret() is True, the raw
    uploader is replaced by a "✅ 등록됨" status + a "교체" button that
    reveals the uploader only when the person explicitly wants to swap
    the file (mirrors the same pattern app/main.py already uses for the
    Suno/OpenAI/Gemini/Apiframe credential fields).
  * SHARED — one render function used by both the Settings page and the
    YouTube Package tab, so the two can never show conflicting status.
  * key_ns-namespaced — safe to render on two different pages in the same
    session without widget-key collisions.
"""
from __future__ import annotations

import streamlit as st


def render_oauth_account_panel(key_ns: str = "yt") -> dict:
    """
    Render the OAuth account section (dependency check, client_secret
    upload/replace, authorize/test/revoke buttons).

    Returns the current oauth.get_auth_status() dict for the caller.
    """
    from services.youtube import oauth_service as oauth
    from services.youtube import token_store as ts
    from services.youtube import dependency_check as DEP

    dep_report = DEP.check_youtube_api_dependencies()
    libs_ok = dep_report["available"]
    if libs_ok:
        st.success("✅ YouTube API dependencies: Ready — 실제 업로드 가능")
    else:
        st.error("❌ YouTube API dependencies: Missing")
        st.caption("실제 YouTube 업로드를 위해 google-api-python-client / "
                   "google-auth-oauthlib 설치가 필요합니다. "
                   "pip install -r requirements.txt 실행 후 다시 시도하세요.")
        st.caption(f"누락 패키지: {', '.join(dep_report['missing'])}")
        st.code("pip install -r requirements.txt")

    status = oauth.get_auth_status()
    st.caption(f"상태: {ts.STATUS_LABELS.get(status.get('status'), status.get('status'))}")
    msg = status.get("message", "")
    if msg and status.get("status") == ts.STATUS_FAILED:
        st.error(msg)
    elif msg and status.get("status") == ts.STATUS_CLIENT_LOADED and "⚠️" in msg:
        st.warning(msg)  # client_secret type hint (web vs. installed)

    # ── client_secret.json — persisted-aware (no forced re-upload) ────────
    show_upload_key = f"{key_ns}_show_client_upload"
    already_loaded = ts.has_client_secret()

    if already_loaded and not st.session_state.get(show_upload_key, False):
        col_status, col_swap = st.columns([3, 1])
        with col_status:
            st.markdown("<div style='color:var(--success);font-size:0.85rem;"
                        "padding-top:6px'>✅ client_secret.json 등록됨 (로컬 저장, "
                        "다시 업로드할 필요 없음)</div>", unsafe_allow_html=True)
        with col_swap:
            if st.button("교체", key=f"{key_ns}_client_swap", use_container_width=True):
                st.session_state[show_upload_key] = True
                st.rerun()
    else:
        client_file = st.file_uploader("client_secret.json 업로드", type=["json"],
                                       key=f"{key_ns}_client_secret_file")
        if client_file is not None:
            if oauth.load_client_secret_from_bytes(client_file.getvalue()):
                st.success("client_secret.json 로드됨 (로컬 저장, 이후 다시 "
                           "업로드하지 않아도 됩니다)")
                st.session_state[show_upload_key] = False
                st.rerun()
            else:
                st.error("유효한 client_secret.json이 아닙니다")
        if already_loaded:
            st.caption("이미 등록된 파일을 유지하려면 새 파일을 선택하지 말고 "
                       "페이지를 벗어나세요.")

    ocol1, ocol2, ocol3 = st.columns(3)
    with ocol1:
        oauth_hint = DEP.oauth_install_hint()
        if st.button("🔑 YouTube 인증", key=f"{key_ns}_authorize",
                     use_container_width=True, disabled=bool(oauth_hint)):
            with st.spinner("브라우저에서 Google 로그인 창이 열립니다 — 완료할 때까지 "
                            "최대 2분 기다립니다. 창이 자동으로 열리지 않으면 이 앱을 "
                            "실행한 터미널(cmd/PowerShell)에 출력된 링크를 확인하세요."):
                res = oauth.authorize()
            (st.error if res.get("status") == ts.STATUS_FAILED else st.success)(
                res.get("message", ""))
        if oauth_hint:
            st.caption(f"⚠️ {oauth_hint}")
    with ocol2:
        if st.button("🔌 연결 테스트", key=f"{key_ns}_test_conn", use_container_width=True):
            r = oauth.test_connection()
            (st.success if r["ok"] else st.warning)(r["message"])
    with ocol3:
        if st.button("🗑️ 토큰 삭제", key=f"{key_ns}_revoke", use_container_width=True):
            oauth.revoke()
            st.caption("로컬 토큰이 삭제되었습니다")

    return status
