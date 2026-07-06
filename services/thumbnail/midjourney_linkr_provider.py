"""
services/thumbnail/midjourney_linkr_provider.py — Midjourney image generation
via LinkrAPI (https://linkrapi.com), a REST proxy over the user's own
Midjourney account.

v1.0.0-alpha.73. This is a SEPARATE provider from the existing
services/thumbnail/midjourney_provider.py (which drives Midjourney via
Apiframe v2 and returns a 4-image grid directly). LinkrAPI instead uses the
classic Midjourney async grid→upscale flow, so it needs its own imagine →
fetch → upscale(action) → fetch → download pipeline.

Flow (LinkrAPI — schema CONFIRMED by a real-key smoke test v1.0.0-alpha.73):
  1. POST  https://linkrapi.com/api/v1/imagine   {"prompt": "...  --ar 16:9 --no text"}
        → {"status": "SUCCESS", "task_id": "<uuid>", "message": "..."}   (2x2 grid job)
  2. GET   https://linkrapi.com/api/v1/fetch/{task_id}   (poll, up to 6 min)
        status seen: "sending" → "starting" → "completed" (in-progress values
        vary; anything not a completion/failure marker keeps polling).
        completed response carries: image_url, images[] (the 4 pre-split
        quadrant URLs _1.._4.png), grid_url, cdn_url, and components[] —
        each {"custom_id": "MJ::JOB::upsample::N::<uuid>", "label": "UN"}.
  3. POST  https://linkrapi.com/api/v1/action  {"task_id": "<grid uuid>",
        "action": "MJ::JOB::upsample::1::<uuid>"}   ← must be the button's
        custom_id, NOT the "U1" label (the label 400s "Action not found in
        task components"). → {"status": "SUCCESS", "task_id": "<upscale uuid>"}
  4. GET   https://linkrapi.com/api/v1/fetch/{task_id}   (poll, up to 4 min)
        → completed with the single upscaled image_url.
  5. Download that image_url → out_path.

  Fallback: LinkrAPI already pre-splits the grid into 4 quadrant images, so if
  the upscale can't proceed (no matching component, action error, or upscale
  timeout) we download images[index] from the grid instead of hard-failing.

  Response parsing stays lenient (_extract_* helpers tolerate casing/nesting
  variants) as cheap insurance, but the shapes above are what the live API
  returns.

Auth: Authorization: Bearer <LINKRAPI_API_KEY>. The key is NEVER logged and is
masked out of any surfaced error text (same rule as every other provider).

Notes:
  * ref_image_path is ignored (Midjourney has no local-file image-to-image
    here); the 1:1 cover is derived by center-crop downstream, as with the
    Apiframe MJ provider.
  * negative_prompt → Midjourney's native ``--no`` param; aspect → ``--ar``.
  * Third-party Midjourney APIs (Apiframe/LinkrAPI/…) are unofficial —
    Midjourney has no public API. Same accepted-risk category as suno-cli.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from services.thumbnail.image_provider import ImageGenProvider, _finalize_image

logger = logging.getLogger(__name__)

# Confirmed from https://linkrapi.com/docs. Override with LINKRAPI_BASE_URL.
_DEFAULT_BASE_URL = "https://linkrapi.com/api/v1"
_KEY_ENV_VAR = "LINKRAPI_API_KEY"

# Midjourney is slow and two-staged (grid, then upscale). Stage the timeouts
# so a stall in either stage is bounded and reported — overridable via env.
_DEFAULT_IMAGINE_TIMEOUT = 360   # 6 min for the initial 2x2 grid
_DEFAULT_UPSCALE_TIMEOUT = 240   # 4 min for the U1 upscale
_DEFAULT_POLL_INTERVAL = 5       # seconds between fetch polls

# Status vocabulary (broad, case-insensitive) — matching only "completed" would
# risk an infinite wait if LinkrAPI returns "success"/"done"; missing a failure
# value would ALSO hang forever, so both sets are intentionally generous.
_COMPLETE_MARKERS = {"completed", "complete", "success", "succeeded", "done", "finished"}
_FAILURE_MARKERS = {"failed", "failure", "error", "errored", "moderated", "banned",
                    "rejected", "cancelled", "canceled"}
# Policy-rejection subset — surfaced to the user with a clear explanation.
_MODERATED_MARKERS = {"moderated", "banned", "rejected"}


class LinkrApiError(RuntimeError):
    """Raised inside the pipeline; generate() converts it to a result dict."""


class LinkrApiTransientError(LinkrApiError):
    """A retryable failure — the request itself is fine, the account/queue
    just returned a one-time/transient state (e.g. Midjourney's 'Thank you
    for subscribing' onboarding banner). generate() retries these."""


# Midjourney sometimes replies to the FIRST /imagine after a (re)subscribe
# with a one-time onboarding banner instead of generating — LinkrAPI then
# reports the job as failed. That's not a real failure: the banner shows once,
# so retrying almost always produces a real image. Matched case-insensitively
# against the failure detail text. Configurable retry count/backoff below.
_TRANSIENT_MARKERS = (
    "thank you for subscribing",
    "you are now subscribed",
    "subscribe to midjourney",
    "your subscription",
)
_TRANSIENT_BACKOFF_SEC = (8, 15, 25)


def _is_transient_failure(detail: str) -> bool:
    low = (detail or "").lower()
    return any(m in low for m in _TRANSIENT_MARKERS)


def _transient_retries() -> int:
    """Extra attempts on a transient (onboarding-banner) failure —
    SEOUL_MJ_LINKR_TRANSIENT_RETRIES, default 2 extra (3 total)."""
    try:
        return max(0, int(os.environ.get("SEOUL_MJ_LINKR_TRANSIENT_RETRIES", "2")))
    except ValueError:
        return 2


def get_linkrapi_key() -> str | None:
    """Return the LinkrAPI API key, or None. Never logged."""
    val = os.environ.get(_KEY_ENV_VAR, "")
    return val.strip() or None


def _base_url() -> str:
    return (os.environ.get("LINKRAPI_BASE_URL", "").strip() or _DEFAULT_BASE_URL).rstrip("/")


def _imagine_timeout() -> int:
    try:
        return max(30, int(os.environ.get("SEOUL_MJ_LINKR_IMAGINE_TIMEOUT", str(_DEFAULT_IMAGINE_TIMEOUT))))
    except ValueError:
        return _DEFAULT_IMAGINE_TIMEOUT


def _upscale_timeout() -> int:
    try:
        return max(30, int(os.environ.get("SEOUL_MJ_LINKR_UPSCALE_TIMEOUT", str(_DEFAULT_UPSCALE_TIMEOUT))))
    except ValueError:
        return _DEFAULT_UPSCALE_TIMEOUT


def _poll_interval() -> int:
    try:
        return max(1, int(os.environ.get("SEOUL_MJ_LINKR_POLL_INTERVAL", str(_DEFAULT_POLL_INTERVAL))))
    except ValueError:
        return _DEFAULT_POLL_INTERVAL


def _mask(text: str, secret: str | None) -> str:
    """Remove the API key from any surfaced text."""
    if secret and secret in text:
        return text.replace(secret, "***")
    return text


# ── Prompt shaping (Midjourney params go in the prompt text) ─────────────────

def _aspect_flag(aspect: str) -> str:
    return {"16:9": "--ar 16:9", "1:1": "--ar 1:1", "9:16": "--ar 9:16"}.get(aspect, "--ar 16:9")


def _mj_style_params() -> str:
    """
    Midjourney-specific style params appended for this provider only (the
    prompt BODY stays provider-neutral, from form_prompt_builder). Defaults
    to a citypop-appropriate `--style raw --stylize 120` (the 110-140 range
    noted in the handoff MV-prompt rules); override or disable via
    SEOUL_MJ_LINKR_STYLE_PARAMS (set it to an empty string to turn off).
    """
    val = os.environ.get("SEOUL_MJ_LINKR_STYLE_PARAMS")
    if val is None:
        return "--style raw --stylize 120"
    return val.strip()


def _to_mj_no(negative_prompt: str) -> str:
    """
    Convert a natural-language negative list into Midjourney ``--no`` terms.

    form_prompt_builder / prompt_generator produce negatives like
    "no text, no letters, no watermark, no logo" — feeding that verbatim into
    ``--no`` would double-negate ("--no no text ..."). Strip the leading
    "no "/"not " from each comma term, drop blanks, and de-dup (order kept)
    so it becomes "text, letters, watermark, logo".
    """
    out: list[str] = []
    seen = set()
    for raw in (negative_prompt or "").split(","):
        term = raw.strip()
        low = term.lower()
        if low.startswith("no "):
            term = term[3:].strip()
        elif low.startswith("not "):
            term = term[4:].strip()
        if term and term.lower() not in seen:
            seen.add(term.lower())
            out.append(term)
    return ", ".join(out)


def _build_prompt(prompt: str, negative_prompt: str, aspect: str) -> str:
    """
    Assemble the full Midjourney prompt: neutral body + ``--ar`` + optional
    style params + ``--no`` (converted from the natural-language negatives).
    """
    parts = [prompt.strip(), _aspect_flag(aspect)]
    style = _mj_style_params()
    if style:
        parts.append(style)
    neg = _to_mj_no(negative_prompt)
    if neg:
        parts.append(f"--no {neg}")
    return " ".join(p for p in parts if p)


# ── Response parsing ─────────────────────────────────────────────────────────
# The live API (confirmed by smoke test) uses top-level task_id / status /
# image_url / images[] / components[]. These helpers stay tolerant of casing
# and nesting variants as cheap insurance against minor API drift.

def _extract_task_id(data) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("task_id", "taskId", "taskID", "id", "jobId", "job_id"):
        v = data.get(key)
        if v:
            return str(v)
    for holder in ("data", "result", "task"):
        inner = data.get(holder)
        if isinstance(inner, dict):
            got = _extract_task_id(inner)
            if got:
                return got
    return None


def _extract_status(data) -> str:
    if not isinstance(data, dict):
        return ""
    for key in ("status", "state", "job_status", "jobStatus"):
        v = data.get(key)
        if v:
            return str(v).strip().lower()
    for holder in ("data", "result", "task"):
        inner = data.get(holder)
        if isinstance(inner, dict):
            got = _extract_status(inner)
            if got:
                return got
    return ""


def _extract_image_url(data) -> str | None:
    """Find the completed image URL across the likely field shapes."""
    if not isinstance(data, dict):
        return None
    for key in ("image_url", "imageUrl", "imageURL", "url", "image", "upscaled_url",
                "upscaledUrl", "output_url", "outputUrl"):
        v = data.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
    # images array — list of urls, or list of {url:...}
    imgs = data.get("images") or data.get("image_urls") or data.get("imageUrls")
    if isinstance(imgs, list) and imgs:
        first = imgs[0]
        if isinstance(first, str) and first.startswith("http"):
            return first
        if isinstance(first, dict):
            got = _extract_image_url(first)
            if got:
                return got
    for holder in ("data", "result", "task", "output"):
        inner = data.get(holder)
        if isinstance(inner, dict):
            got = _extract_image_url(inner)
            if got:
                return got
    return None


def _extract_error(data) -> str:
    if not isinstance(data, dict):
        return ""
    for key in ("error", "message", "detail", "reason", "failure_reason", "failureReason"):
        v = data.get(key)
        if v:
            return str(v)
    for holder in ("data", "result", "task"):
        inner = data.get(holder)
        if isinstance(inner, dict):
            got = _extract_error(inner)
            if got:
                return got
    return ""


def _upscale_label_for_index(index: int) -> str:
    """index 0→U1, 1→U2, 2→U3, 3→U4 (clamped). Default/quadrant-0 = U1 (top-left)."""
    n = min(4, max(1, int(index) + 1))
    return f"U{n}"


def _extract_components(data) -> list[dict]:
    """The completed grid's action buttons (each {custom_id, label, ...})."""
    if not isinstance(data, dict):
        return []
    comps = data.get("components")
    if isinstance(comps, list):
        return [c for c in comps if isinstance(c, dict)]
    for holder in ("data", "result", "task"):
        inner = data.get(holder)
        if isinstance(inner, dict):
            got = _extract_components(inner)
            if got:
                return got
    return []


def _find_upscale_custom_id(components: list[dict], index: int) -> str | None:
    """
    Find the upscale button's custom_id for quadrant U{index+1}.

    Confirmed shape (real LinkrAPI fetch response):
      {"custom_id": "MJ::JOB::upsample::1::<uuid>", "label": "U1", "style": 2}
    LinkrAPI's POST /action matches on the custom_id (NOT the "U1" label —
    passing the label yields 400 "Action not found in task components").
    Prefer an exact label match; fall back to the "upsample::<n>::" tag.
    """
    label = _upscale_label_for_index(index)          # "U1".."U4"
    n = label[1:]                                    # "1".."4"
    for c in components:
        if str(c.get("label", "")).strip().upper() == label:
            cid = c.get("custom_id")
            if cid:
                return str(cid)
    for c in components:
        cid = str(c.get("custom_id", ""))
        if f"upsample::{n}::" in cid.lower() or f"upsample::{n}:" in cid.lower():
            return cid
    return None


def _extract_grid_images(data) -> list[str]:
    """The 4 already-split quadrant image URLs from the completed grid
    (LinkrAPI pre-splits: images[0..3] = the four U-quadrants). Used as a
    graceful fallback when the upscale action can't proceed."""
    if not isinstance(data, dict):
        return []
    imgs = data.get("images")
    if isinstance(imgs, list):
        urls = [u for u in imgs if isinstance(u, str) and u.startswith("http")]
        if urls:
            return urls
    for holder in ("data", "result", "task"):
        inner = data.get(holder)
        if isinstance(inner, dict):
            got = _extract_grid_images(inner)
            if got:
                return got
    return []


class MidjourneyLinkrProvider(ImageGenProvider):
    """Real generation on the user's Midjourney account via LinkrAPI."""

    name = "midjourney-linkr"
    is_real = True

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or get_linkrapi_key()
        self.model = "midjourney"

    # ── HTTP helpers ─────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {"Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}"}

    def _submit_imagine(self, prompt: str):
        """POST /imagine → task_id (raises LinkrApiError on failure)."""
        import requests
        url = f"{_base_url()}/imagine"
        try:
            resp = requests.post(url, headers=self._headers(),
                                 json={"prompt": prompt}, timeout=60)
        except Exception as e:
            raise LinkrApiError(_mask(f"imagine request failed: {type(e).__name__}: {e}", self._api_key))
        if resp.status_code not in (200, 201, 202):
            raise LinkrApiError(_mask(f"imagine HTTP {resp.status_code}: {resp.text[:300]}", self._api_key))
        try:
            data = resp.json()
        except Exception:
            raise LinkrApiError("imagine returned invalid JSON")
        task_id = _extract_task_id(data)
        if not task_id:
            raise LinkrApiError(_mask(f"imagine returned no task_id: {str(data)[:300]}", self._api_key))
        return task_id

    def _submit_action(self, task_id: str, action: str):
        """POST /action {task_id, action} → new task_id (raises on failure)."""
        import requests
        url = f"{_base_url()}/action"
        try:
            resp = requests.post(url, headers=self._headers(),
                                 json={"task_id": task_id, "action": action}, timeout=60)
        except Exception as e:
            raise LinkrApiError(_mask(f"action request failed: {type(e).__name__}: {e}", self._api_key))
        if resp.status_code not in (200, 201, 202):
            raise LinkrApiError(_mask(f"action HTTP {resp.status_code}: {resp.text[:300]}", self._api_key))
        try:
            data = resp.json()
        except Exception:
            raise LinkrApiError("action returned invalid JSON")
        # Some proxies return the new task_id; others may complete inline and
        # already carry the image. Prefer a new task_id, else signal "inline".
        new_task_id = _extract_task_id(data)
        inline_url = _extract_image_url(data)
        return new_task_id, inline_url

    def _poll_fetch(self, task_id: str, timeout_sec: int, stage: str):
        """
        Poll GET /fetch/{task_id} until a completion/failure status.
        Returns the final response dict. Raises LinkrApiError on failure
        status, timeout, or a moderated/banned (policy) rejection.

        stage is "imagine" or "upscale" — used only for progress logging so
        the user can tell polling is alive rather than stuck.
        """
        import requests
        url = f"{_base_url()}/fetch/{task_id}"
        start = time.time()
        interval = _poll_interval()
        last_status = "pending"
        while True:
            elapsed = int(time.time() - start)
            if elapsed >= timeout_sec:
                raise LinkrApiError(
                    f"{stage} timed out after {timeout_sec}s (last status: {last_status})")
            try:
                resp = requests.get(url, headers=self._headers(), timeout=30)
            except Exception as e:
                # transient network error — log and keep polling until deadline
                last_status = f"poll error: {type(e).__name__}"
                logger.info("MJ(LinkrAPI) %s 폴링 중 (%d초 경과) — %s", stage, elapsed, last_status)
                time.sleep(interval)
                continue

            if resp.status_code != 200:
                last_status = f"HTTP {resp.status_code}"
                logger.info("MJ(LinkrAPI) %s 폴링 중 (%d초 경과) — %s", stage, elapsed, last_status)
                time.sleep(interval)
                continue
            try:
                data = resp.json()
            except Exception:
                logger.info("MJ(LinkrAPI) %s 폴링 중 (%d초 경과) — invalid JSON", stage, elapsed)
                time.sleep(interval)
                continue

            status = _extract_status(data)
            last_status = status or "unknown"

            # ── 3-way branch (order matters: check failure before "keep going") ──
            if status in _FAILURE_MARKERS:
                if status in _MODERATED_MARKERS:
                    detail = _extract_error(data)
                    raise LinkrApiError(
                        "프롬프트가 정책 위반으로 거부되었습니다 (Midjourney moderation: "
                        f"'{status}'). 프롬프트 문구를 수정해 다시 시도하세요."
                        + (f" — {_mask(detail, self._api_key)[:200]}" if detail else ""))
                detail = _extract_error(data) or "unknown error"
                msg = _mask(f"{stage} failed (status={status}): {detail[:300]}", self._api_key)
                # One-time Midjourney onboarding banner → retryable, not fatal.
                if _is_transient_failure(detail):
                    raise LinkrApiTransientError(msg)
                raise LinkrApiError(msg)

            if status in _COMPLETE_MARKERS:
                logger.info("MJ(LinkrAPI) %s 완료 (%d초 경과, status=%s)", stage, elapsed, status)
                return data

            # otherwise: pending / processing / queued / unknown → keep polling
            logger.info("MJ(LinkrAPI) %s 폴링 중 (%d초 경과) — status=%s", stage, elapsed, last_status)
            time.sleep(interval)

    def _download(self, url: str, out: Path):
        """Download the final image URL to out (raises on failure)."""
        import requests
        try:
            resp = requests.get(url, timeout=120)
        except Exception as e:
            raise LinkrApiError(_mask(f"image download failed: {type(e).__name__}: {e}", self._api_key))
        if resp.status_code != 200:
            raise LinkrApiError(f"image download HTTP {resp.status_code}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(resp.content)

    # ── ImageGenProvider interface ───────────────────────────────────────

    def generate(self, prompt, out_path, negative_prompt="", index=0, meta=None,
                 aspect="16:9", ref_image_path=None):
        if not self._api_key:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None,
                    "error": "no API key (enter the LinkrAPI key in the sidebar 🎨 Image Gen, "
                             "or set LINKRAPI_API_KEY)"}

        full_prompt = _build_prompt(prompt, negative_prompt, aspect)
        out = Path(out_path)

        # Retry the WHOLE imagine→upscale cycle on a transient failure (e.g.
        # Midjourney's one-time 'Thank you for subscribing' onboarding banner,
        # which LinkrAPI reports as status=failed but clears on the next call).
        attempts = _transient_retries() + 1
        grid_task_id = None
        last_transient = None
        for attempt in range(attempts):
            try:
                grid_task_id = self._run_pipeline(full_prompt, out, index, aspect)
            except LinkrApiTransientError as e:
                last_transient = str(e)
                if attempt < attempts - 1:
                    delay = _TRANSIENT_BACKOFF_SEC[min(attempt, len(_TRANSIENT_BACKOFF_SEC) - 1)]
                    logger.info("MJ(LinkrAPI) 일시적 실패(온보딩 배너 등) — %d초 후 재시도 %d/%d",
                                delay, attempt + 2, attempts)
                    time.sleep(delay)
                    continue
                # exhausted retries — surface a helpful message
                return {"ok": False, "provider": self.name, "model": self.model,
                        "path": None,
                        "error": (f"{last_transient} — 재시도 {attempts}회 모두 같은 응답. "
                                  "Midjourney 계정 온보딩이 안 끝났을 수 있습니다. LinkrAPI에 연결된 "
                                  "Discord에서 봇 DM으로 /imagine을 한 번 직접 실행한 뒤 다시 시도하세요."),
                        "task_id": grid_task_id}
            except LinkrApiError as e:
                return {"ok": False, "provider": self.name, "model": self.model,
                        "path": None, "error": str(e), "task_id": grid_task_id}
            except Exception as e:  # pragma: no cover - unexpected
                return {"ok": False, "provider": self.name, "model": self.model,
                        "path": None,
                        "error": _mask(f"unexpected error: {type(e).__name__}: {e}", self._api_key),
                        "task_id": grid_task_id}
            # success
            _finalize_image(str(out), aspect)  # strip stray bars + lock exact size
            return {"ok": True, "provider": self.name, "model": self.model,
                    "path": str(out), "error": None, "task_id": grid_task_id}

    def _run_pipeline(self, full_prompt: str, out: Path, index: int, aspect: str) -> str:
        """imagine → poll → upscale(U{n} via custom_id) → poll → download.
        Returns the grid task_id. Raises LinkrApiTransientError on a retryable
        state, LinkrApiError else. Falls back to the pre-split grid quadrant
        image when the upscale can't proceed (an image is already in hand)."""
        # 1) imagine → grid job
        grid_task_id = self._submit_imagine(full_prompt)
        logger.info("MJ(LinkrAPI) imagine 제출됨 (task_id=%s) — 그리드 생성 대기 시작", grid_task_id)
        grid = self._poll_fetch(grid_task_id, _imagine_timeout(), "imagine")

        # 2) upscale quadrant U{index+1}. LinkrAPI's /action needs the button's
        #    custom_id from the grid's components (the plain "U1" label 400s).
        label = _upscale_label_for_index(index)
        custom_id = _find_upscale_custom_id(_extract_components(grid), index)
        image_url = None
        if custom_id:
            try:
                up_task_id, inline_url = self._submit_action(grid_task_id, custom_id)
                logger.info("MJ(LinkrAPI) %s 업스케일 요청됨 (custom_id 사용, task_id=%s)",
                            label, up_task_id or "inline")
                if inline_url and not up_task_id:
                    image_url = inline_url
                else:
                    final = self._poll_fetch(up_task_id, _upscale_timeout(), "upscale")
                    image_url = _extract_image_url(final)
            except LinkrApiError as e:
                logger.info("MJ(LinkrAPI) 업스케일 실패(%s) — 그리드 분할 이미지로 폴백", e)

        if not image_url:
            # Fallback: LinkrAPI pre-splits the grid into 4 quadrant images, so
            # images[index] is already a usable single image at grid resolution.
            grid_imgs = _extract_grid_images(grid)
            if grid_imgs:
                image_url = grid_imgs[min(index, len(grid_imgs) - 1)]
                logger.info("MJ(LinkrAPI) 그리드 분할 이미지(quadrant %d) 사용", min(index, len(grid_imgs) - 1) + 1)
            else:
                image_url = _extract_image_url(grid)  # last resort: top-level image_url
        if not image_url:
            raise LinkrApiError("완료됐지만 이미지 URL을 응답에서 찾지 못함")

        # 3) download → out_path
        self._download(image_url, out)
        return grid_task_id


def verify_linkrapi_key(key: str) -> tuple[bool, str]:
    """
    Lightweight credential check for the sidebar field. Public docs don't
    document a dedicated /me endpoint, so we just confirm the key shape and
    that the base host is reachable — a definitive check happens on the first
    real generation. Never logs the key.
    TODO(linkrapi-schema): swap for a real GET /me (or equivalent) once the
    endpoint is confirmed.
    """
    import requests
    if not key or not key.strip():
        return False, "키가 비어 있습니다"
    key = key.strip()
    if not key.startswith("lkr_"):
        return False, "LinkrAPI 키는 보통 'lkr_'로 시작합니다 — 키를 다시 확인하세요"
    try:
        # HEAD the base host just to confirm connectivity (no auth-specific route
        # is documented publicly). A 2xx/3xx/4xx all prove reachability.
        resp = requests.get(_base_url().rsplit("/api", 1)[0], timeout=10)
        if resp.status_code < 500:
            return True, "키 형식 확인됨 (실제 유효성은 첫 생성 시 확정됩니다)"
        return False, f"LinkrAPI 응답 오류 HTTP {resp.status_code}"
    except Exception as e:
        return False, f"연결 실패: {type(e).__name__}: {_mask(str(e), key)}"
