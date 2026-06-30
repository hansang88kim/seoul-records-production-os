"""
services/thumbnail/image_provider.py — real thumbnail-image generation.

Turns a Google-Flow-style prompt (from prompt_generator) into an ACTUAL image
file. Two providers behind one interface:

  * MockImageGenProvider  — default. Writes a deterministic PIL placeholder PNG
    (citypop-tinted, scene text baked in) so the whole pipeline + tests run with
    zero network access and zero cost.
  * GeminiImageProvider   — real. Calls the OFFICIAL Google Gemini API (the same
    image model Google Flow uses under the hood, "Nano Banana" =
    gemini-2.5-flash-image; Imagen 4 also supported). API-key auth only, no
    browser automation, no CAPTCHA solving. The google-genai SDK is imported
    lazily so this module loads fine when the SDK is absent.

Provider selection: get_image_provider(use_real=...) returns the Gemini provider
only when use_real is True AND the SDK + an API key are present; otherwise it
falls back to the mock. Tests must NEVER hit the real provider.
"""
from __future__ import annotations

import os
from pathlib import Path

# Default real model = "Nano Banana" (free tier on the Gemini API). Override with
# SEOUL_IMAGE_MODEL, e.g. "imagen-4.0-fast-generate-001".
DEFAULT_IMAGE_MODEL = "gemini-2.5-flash-image"
# Checked in order. GOOGLE_GEMINI_API_KEY is what the app's sidebar credential
# field stores, so the key entered in the left panel is picked up automatically.
_API_KEY_ENV_VARS = (
    "GOOGLE_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY",
)
# Real backend: "rest" (default, requests-only — no extra install) or "sdk"
# (google-genai; also enables Imagen). Override with SEOUL_IMAGE_BACKEND.
_GEMINI_REST_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)

# Citypop palette for the mock placeholder (neon magenta / cyan / amber on night).
_MOCK_BG = (18, 22, 38)
_MOCK_ACCENTS = [(0, 212, 255), (255, 64, 129), (255, 176, 32), (124, 92, 255)]


def get_api_key() -> str | None:
    """Return the first configured Gemini API key, or None. Never logged."""
    for var in _API_KEY_ENV_VARS:
        val = os.environ.get(var)
        if val and val.strip():
            return val.strip()
    return None


# Native generation sizes per aspect. We generate each deliverable at its OWN
# aspect ratio (never stretch a 16:9 into a 1:1) — the YouTube thumbnail is 16:9
# and the streaming cover is 1:1. Final exporters upscale from these.
_ASPECT_DIMS = {
    "16:9": (1280, 720),
    "1:1": (1024, 1024),
    "9:16": (720, 1280),
}


def _aspect_dims(aspect: str) -> tuple[int, int]:
    return _ASPECT_DIMS.get(aspect, _ASPECT_DIMS["16:9"])


def _autotrim_bars(img):
    """Trim uniform letterbox/pillarbox bars (e.g. white/black) the model may add.

    Conservative: only trims when a border band is near-uniform and matches a
    corner colour, so normal night scenes (dark/neon corners) are left untouched.
    """
    from PIL import Image, ImageChops
    try:
        corner = img.getpixel((1, 1))
        bg = Image.new(img.mode, img.size, corner)
        bbox = ImageChops.difference(img, bg).convert("L").getbbox()
        if bbox:
            l, t, r, b = bbox
            w, h = img.size
            # Require the trim to look like real bars (covers most of a side) and
            # not a tiny speck or an aggressive crop of a busy image.
            if (t > 2 or (h - b) > 2 or l > 2 or (w - r) > 2):
                if (r - l) >= w * 0.5 and (b - t) >= h * 0.5:
                    return img.crop(bbox)
    except Exception:
        pass
    return img


def _cover_to(img, tw: int, th: int):
    """Scale to COVER the target then center-crop to exact (tw, th) — no stretch."""
    from PIL import Image
    w, h = img.size
    if w == tw and h == th:
        return img
    scale = max(tw / w, th / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    x, y = (nw - tw) // 2, (nh - th) // 2
    return img.crop((x, y, x + tw, y + th))


def _finalize_image(path: str, aspect: str):
    """Post-process a generated file: strip stray bars + lock to the exact native
    size for its aspect (center-crop cover, never stretch). Best-effort."""
    try:
        from PIL import Image
        tw, th = _aspect_dims(aspect)
        img = Image.open(path).convert("RGB")
        img = _autotrim_bars(img)
        img = _cover_to(img, tw, th)
        img.save(path, format="PNG")
    except Exception:
        pass  # never fail generation over post-processing


class ImageGenProvider:
    """Abstract image-generation provider."""

    name = "base"
    is_real = False

    def generate(
        self,
        prompt: str,
        out_path: str,
        negative_prompt: str = "",
        index: int = 0,
        meta: dict | None = None,
        aspect: str = "16:9",
        ref_image_path: str | None = None,
    ) -> dict:
        """Generate one image to out_path at the given ``aspect`` ratio.

        ``aspect`` is "16:9" (default) or "1:1". ``ref_image_path`` optionally
        supplies a reference image for image-to-image (used to recompose the same
        scene into a different aspect). Returns a result dict with keys: ok (bool),
        provider (str), model (str | None), path (str | None), error (str | None).
        """
        raise NotImplementedError


class MockImageGenProvider(ImageGenProvider):
    """Writes a deterministic placeholder PNG — no network, no cost."""

    name = "mock"
    is_real = False

    def generate(self, prompt, out_path, negative_prompt="", index=0, meta=None,
                 aspect="16:9", ref_image_path=None):
        meta = meta or {}
        try:
            from PIL import Image, ImageDraw, ImageFont
        except Exception as e:  # pragma: no cover - PIL is a declared dep
            return {"ok": False, "provider": self.name, "model": None,
                    "path": None, "error": f"PIL unavailable: {e}"}

        W, H = _aspect_dims(aspect)  # native canvas for the requested ratio
        accent = _MOCK_ACCENTS[index % len(_MOCK_ACCENTS)]
        img = Image.new("RGB", (W, H), _MOCK_BG)
        draw = ImageDraw.Draw(img, "RGBA")

        # Simple gradient-ish night wash + accent glow blocks (placeholder vibe).
        for y in range(0, H, 4):
            shade = int(10 + 22 * (y / H))
            draw.line([(0, y), (W, y)], fill=(shade, shade + 4, shade + 14))
        draw.rectangle([0, H - 150, W, H], fill=(*accent, 38))
        draw.ellipse([W - 360, -120, W + 120, 240], fill=(*accent, 30))

        def _font(sz):
            for fp in (
                r"C:\Windows\Fonts\malgunbd.ttf",
                r"C:\Windows\Fonts\malgun.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ):
                try:
                    return ImageFont.truetype(fp, sz)
                except Exception:
                    continue
            return ImageFont.load_default()

        scene = str(meta.get("scene", ""))[:48]
        country = str(meta.get("country", ""))
        theme = str(meta.get("theme", ""))[:40]
        draw.text((48, 40), "MOCK THUMBNAIL", font=_font(40), fill=(*accent, 255))
        draw.text((48, 96), f"{country} · {theme}", font=_font(26), fill=(220, 224, 235, 255))
        if scene:
            draw.text((48, 150), scene, font=_font(22), fill=(170, 178, 198, 255))
        draw.text((48, H - 60), f"candidate #{index + 1}", font=_font(22),
                  fill=(150, 158, 178, 255))

        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out, format="PNG")
        return {"ok": True, "provider": self.name, "model": "mock-placeholder",
                "path": str(out), "error": None}


class GeminiRestImageProvider(ImageGenProvider):
    """Real generation via the Gemini REST API using `requests` only.

    No extra install required (mirrors the app's existing Gemini REST calls). The
    key comes from the sidebar / env (GOOGLE_GEMINI_API_KEY etc.) and is NEVER
    logged. Works with Gemini image models (e.g. gemini-2.5-flash-image); for
    Imagen models use the SDK backend instead.
    """

    name = "gemini-rest"
    is_real = True

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or os.environ.get("SEOUL_IMAGE_MODEL", DEFAULT_IMAGE_MODEL)
        self._api_key = api_key or get_api_key()

    def generate(self, prompt, out_path, negative_prompt="", index=0, meta=None,
                 aspect="16:9", ref_image_path=None):
        if not self._api_key:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": "no API key (enter Gemini key in the sidebar)"}
        if self.model.startswith("imagen"):
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None,
                    "error": "Imagen needs the SDK backend (set SEOUL_IMAGE_BACKEND=sdk "
                             "+ pip install google-genai)"}
        try:
            import base64
            import requests
        except Exception as e:  # pragma: no cover
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": f"requests unavailable: {e}"}

        full_prompt = prompt
        if negative_prompt:
            full_prompt = f"{prompt}\n\nAvoid: {negative_prompt}"
        # Frame natively for the target ratio and forbid letterbox bars.
        full_prompt += (
            f"\n\nCompose this for a {aspect} aspect ratio, full-bleed edge to edge. "
            f"The image must completely fill the {aspect} frame with no borders, no "
            f"white or black bars, no letterboxing, no padding."
        )

        parts = [{"text": full_prompt}]
        # Optional image-to-image: recompose the SAME scene into another ratio.
        if ref_image_path:
            try:
                ref_b64 = base64.b64encode(Path(ref_image_path).read_bytes()).decode()
                parts.append({"inlineData": {"mimeType": "image/png", "data": ref_b64}})
            except Exception:
                pass

        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        url = _GEMINI_REST_ENDPOINT.format(model=self.model, key=self._api_key)
        gen_cfg = {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": aspect},
        }
        try:
            def _post(cfg):
                return requests.post(
                    url, headers={"Content-Type": "application/json"},
                    json={"contents": [{"parts": parts}], "generationConfig": cfg},
                    timeout=120,
                )

            resp = _post(gen_cfg)
            # Some model versions reject imageConfig — retry without it (the prompt
            # hint + post-processing still deliver the right aspect, just cropped).
            if resp.status_code == 400 and "imageconfig" in resp.text.lower():
                resp = _post({"responseModalities": ["TEXT", "IMAGE"]})
            if resp.status_code != 200:
                # Surface the API's message WITHOUT echoing the key (which is in the URL).
                msg = resp.text[:300].replace(self._api_key, "***")
                return {"ok": False, "provider": self.name, "model": self.model,
                        "path": None, "error": f"HTTP {resp.status_code}: {msg}"}
            data = resp.json()
            img_b64 = None
            for cand in data.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        img_b64 = inline["data"]
                        break
                if img_b64:
                    break
            if not img_b64:
                return {"ok": False, "provider": self.name, "model": self.model,
                        "path": None, "error": "no image data in response (model may have "
                                               "returned text only)"}
            out.write_bytes(base64.b64decode(img_b64))
            _finalize_image(str(out), aspect)  # strip stray bars + lock exact size
            return {"ok": True, "provider": self.name, "model": self.model,
                    "path": str(out), "error": None}
        except Exception as e:
            safe = str(e).replace(self._api_key, "***") if self._api_key else str(e)
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": f"request failed: {type(e).__name__}: {safe}"}


class GeminiImageProvider(ImageGenProvider):
    """Real generation via the official Google Gemini API (Nano Banana / Imagen).

    Auth: API key from GEMINI_API_KEY / GOOGLE_API_KEY. The key is NEVER logged
    or written to disk. SDK is imported lazily.
    """

    name = "gemini"
    is_real = True

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or os.environ.get("SEOUL_IMAGE_MODEL", DEFAULT_IMAGE_MODEL)
        self._api_key = api_key or get_api_key()

    def generate(self, prompt, out_path, negative_prompt="", index=0, meta=None,
                 aspect="16:9", ref_image_path=None):
        if not self._api_key:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": "no API key (set GEMINI_API_KEY)"}
        try:
            from google import genai  # lazy: only needed for the real path
            from google.genai import types
        except Exception as e:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None,
                    "error": f"google-genai not installed ({e}); pip install google-genai"}

        full_prompt = prompt
        if negative_prompt:
            full_prompt = f"{prompt}\n\nAvoid: {negative_prompt}"
        full_prompt += (
            f"\n\nCompose this for a {aspect} aspect ratio, full-bleed edge to edge — "
            f"no borders, no white or black bars, no letterboxing, no padding."
        )

        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            client = genai.Client(api_key=self._api_key)
            data = None

            if self.model.startswith("imagen"):
                # Dedicated text-to-image (Imagen family).
                resp = client.models.generate_images(
                    model=self.model,
                    prompt=full_prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1, aspect_ratio=aspect,
                    ),
                )
                imgs = getattr(resp, "generated_images", None) or []
                if imgs:
                    data = imgs[0].image.image_bytes
            else:
                # Gemini image model ("Nano Banana") — interleaved generateContent.
                # Pass a reference image (image-to-image) when recomposing a scene.
                contents = [full_prompt]
                if ref_image_path:
                    try:
                        contents.append(types.Part.from_bytes(
                            data=Path(ref_image_path).read_bytes(), mime_type="image/png"))
                    except Exception:
                        pass
                resp = client.models.generate_content(
                    model=self.model, contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                        image_config=types.ImageConfig(aspect_ratio=aspect),
                    ),
                )
                cands = getattr(resp, "candidates", None) or []
                if cands:
                    for part in cands[0].content.parts:
                        inline = getattr(part, "inline_data", None)
                        if inline is not None and getattr(inline, "data", None):
                            data = inline.data
                            break

            if not data:
                return {"ok": False, "provider": self.name, "model": self.model,
                        "path": None, "error": "no image data returned by model"}
            out.write_bytes(data)
            _finalize_image(str(out), aspect)  # strip stray bars + lock exact size
            return {"ok": True, "provider": self.name, "model": self.model,
                    "path": str(out), "error": None}
        except Exception as e:
            # Surface a clean message; never include the API key.
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": f"generation failed: {type(e).__name__}: {e}"}


def get_image_provider(use_real: bool = False, model: str | None = None) -> ImageGenProvider:
    """Return the appropriate provider.

    Real provider only when use_real AND an API key is set; otherwise the mock —
    so tests/default runs never call out. The real backend defaults to REST
    (requests only, no extra install); set SEOUL_IMAGE_BACKEND=sdk to use the
    google-genai SDK (required for Imagen models).
    """
    if not use_real:
        return MockImageGenProvider()
    if not get_api_key():
        return MockImageGenProvider()

    backend = os.environ.get("SEOUL_IMAGE_BACKEND", "rest").strip().lower()
    if backend == "sdk":
        try:
            import google.genai  # noqa: F401
            return GeminiImageProvider(model=model)
        except Exception:
            # SDK requested but unavailable — fall back to REST rather than mock.
            return GeminiRestImageProvider(model=model)
    return GeminiRestImageProvider(model=model)
