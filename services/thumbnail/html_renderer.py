"""
services/thumbnail/html_renderer.py — HTML/CSS + Playwright thumbnail renderer
(v1.0.0-alpha.69).

Replaces the PIL-based services/thumbnail/canva_branding.py renderer with a
server-side port of seoul_records_thumbnail_studio.html (the confirmed design
source of truth — see claude_code_thumbnail_v2_prompt.md). 6 forms (A-F) x 2
ratios (169/11) = 12 layouts, assembled as a static HTML document and shot
with a headless Chromium via Playwright.

Design note on canvas size: the reference HTML's CSS was tuned pixel-by-pixel
(padding:0 60px, font-size:132px, top:24px, ...) for LOGICAL canvases of
1280x720 (16:9) and 1080x1080 (1:1). Rather than recompute every value for a
different logical size, we keep those exact logical dimensions and reach the
real target resolution (services/thumbnail/asset_types.CANVAS_SIZES —
1920x1080 / 3000x3000) purely via Playwright's device_scale_factor. A final
PIL resize guards against float/rounding drift in the scale factor.

canva_branding.py / asset_exporter.py / prompt_generator.py / country_presets.py
are all left untouched — this module is purely additive.
"""
from __future__ import annotations

import base64
import io
import tempfile
import uuid
from pathlib import Path

# ─── Font pools (ported verbatim from FONTS / KR_FONTS in the reference) ────

FONTS = [
    {"name": "Playfair Display (이탤릭 세리프)", "css": "'Playfair Display', serif", "italic": True},
    {"name": "Cormorant Garamond (클래식 세리프)", "css": "'Cormorant Garamond', serif", "italic": True},
    {"name": "Bodoni Moda (하이패션)", "css": "'Bodoni Moda', serif", "italic": False},
    {"name": "DM Serif Display (모던 세리프)", "css": "'DM Serif Display', serif", "italic": False},
    {"name": "Prata (우아한 디돈)", "css": "'Prata', serif", "italic": False},
    {"name": "Marcellus (로만 캐피탈)", "css": "'Marcellus', serif", "italic": False},
    {"name": "Italiana (얇은 세리프)", "css": "'Italiana', serif", "italic": False},
    {"name": "Anton (임팩트 산세리프)", "css": "'Anton', sans-serif", "italic": False},
    {"name": "Bebas Neue (컨덴스드)", "css": "'Bebas Neue', sans-serif", "italic": False},
    {"name": "Montserrat 800 (지오메트릭)", "css": "'Montserrat', sans-serif", "weight": 800, "italic": False},
]

KR_FONTS = [
    {"name": "Noto Sans KR (고딕)", "css": "'Noto Sans KR', sans-serif"},
    {"name": "나눔명조 (세리프)", "css": "'Nanum Myeongjo', serif"},
    {"name": "고운바탕 (모던 명조)", "css": "'Gowun Batang', serif"},
    {"name": "송명 (클래식 명조)", "css": "'Song Myung', serif"},
]

DEFAULT_KR_FONT_CSS = KR_FONTS[0]["css"]

# ─── Form definitions (ported verbatim from FORMS in the reference) ────────
# recFont indexes into FONTS — the per-form recommended title font.

FORMS = {
    "A": {"label": "A 인물형", "rec": "중앙 인물 · 좌우 분할", "recFont": 1, "layout": "split"},
    "B": {"label": "B 배경형", "rec": "풍경 위 중앙 대형 제목", "recFont": 0, "layout": "center"},
    "C": {"label": "C 교차형", "rec": "오브젝트 좌우 · 가운데 &", "recFont": 2, "layout": "split_amp"},
    "D": {"label": "D 뱃지형", "rec": "상단 타원 뱃지 + 중앙 제목", "recFont": 4, "layout": "badge"},
    "E": {"label": "E 플랫레이", "rec": "위에서 본 구도 · 좌우 분할", "recFont": 7, "layout": "split"},
    "F": {"label": "F 아치형", "rec": "제목을 곡선(아치)으로 배치", "recFont": 5, "layout": "arch"},
}

# Forms that get a left vertical spine at 1:1 (JS: hasSpine = form in {A,B}).
SPINE_FORMS = ("A", "B")

# Canvas the reference CSS was tuned for — do not change without re-tuning
# every pixel value below.
_LOGICAL = {"169": (1280, 720), "11": (1080, 1080)}

# Real output resolution (services/thumbnail/asset_types.CANVAS_SIZES).
_TARGET = {"169": (1920, 1080), "11": (3000, 3000)}

GOOGLE_FONTS_HREF = (
    "https://fonts.googleapis.com/css2?"
    "family=Playfair+Display:ital,wght@0,500;0,600;0,700;0,800;1,600;1,700"
    "&family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,600;1,700"
    "&family=Bodoni+Moda:ital,wght@0,500;0,700;1,600"
    "&family=DM+Serif+Display:ital@0;1"
    "&family=Prata&family=Anton&family=Bebas+Neue"
    "&family=Montserrat:wght@400;500;600;700;800"
    "&family=Marcellus&family=Italiana"
    "&family=Noto+Sans+KR:wght@300;400;500;700"
    "&family=Nanum+Myeongjo:wght@400;700;800"
    "&family=Gowun+Batang:wght@400;700"
    "&family=Song+Myung&display=swap"
)


def recommended_font_css(form: str) -> str:
    """The title-font CSS recommended for `form` (FORMS[form].recFont)."""
    return FONTS[FORMS[form]["recFont"]]["css"]


def _font_italic_weight(title_font_css: str) -> tuple[bool, int]:
    """Look up (italic, weight) for a title_font_css string from FONTS,
    falling back to (False, 700) for a font not in the pool (custom CSS)."""
    for f in FONTS:
        if f["css"] == title_font_css:
            return bool(f.get("italic")), int(f.get("weight", 700))
    return False, 700


# ─── Small helpers ───────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    """HTML-escape (mirrors the reference's esc())."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _chunk(items: list[str], n: int) -> list[list[str]]:
    return [items[i:i + n] for i in range(0, len(items), n)]


def _image_data_uri(path: str, max_side: int = 2200) -> str:
    """
    Resize (long side -> max_side) and base64-embed a local image as a data
    URI — recommended over file:// in the spec (fewer load failures).
    """
    from PIL import Image

    img = Image.open(path).convert("RGB")
    w, h = img.size
    scale = max_side / max(w, h)
    if scale < 1:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _cutout_data_uri(path: str) -> str:
    """Base64-embed a (presumably RGBA) cutout PNG, no resize/recompression
    — recompressing a cutout as JPEG would destroy its alpha channel."""
    data = Path(path).read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ─── SVG arch title (ported from archSVG / arch11SVG) ───────────────────────

def _arch_svg_169(w: int, text: str, font_css: str, weight: int, italic: bool, color: str) -> str:
    uid = "arch" + uuid.uuid4().hex[:5]
    cx, y0, rise = w / 2, 480, 155
    d = f"M 150 {y0} Q {cx} {y0 - rise} {w - 150} {y0}"
    style = "italic" if italic else "normal"
    return f"""<div class="arch" style="position:absolute;inset:0;z-index:5;">
    <svg xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="720" viewBox="0 0 {w} 720">
      <defs>
        <path id="{uid}" d="{d}"/>
        <filter id="{uid}s" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#000" flood-opacity="0.8"/>
        </filter>
      </defs>
      <text fill="{color}" font-family="{font_css.replace(chr(39), '')}" font-weight="{weight}" font-style="{style}"
        font-size="128" letter-spacing="1" filter="url(#{uid}s)">
        <textPath href="#{uid}" xlink:href="#{uid}" startOffset="50%" text-anchor="middle">{text}</textPath>
      </text>
    </svg></div>"""


def _arch_svg_11(text: str, font_css: str, color: str) -> str:
    uid = "a11" + uuid.uuid4().hex[:5]
    d = "M 120 640 Q 540 430 960 640"
    return f"""<div style="position:absolute;inset:0;z-index:5;"><svg xmlns:xlink="http://www.w3.org/1999/xlink" width="1080" height="1080" viewBox="0 0 1080 1080" style="overflow:visible">
    <defs><path id="{uid}" d="{d}"/>
    <filter id="{uid}s" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#000" flood-opacity="0.8"/></filter></defs>
    <text fill="{color}" font-family="{font_css.replace(chr(39), '')}" font-weight="700" font-size="118" filter="url(#{uid}s)">
      <textPath href="#{uid}" xlink:href="#{uid}" startOffset="50%" text-anchor="middle">{text}</textPath></text></svg></div>"""


# ─── fitSplit() — ported verbatim, runs client-side after layout ───────────
# (long titles in split/split_amp layouts shrink 6px at a time, floor 48px,
#  until they clear the frame's 54px side margins — real layout measurement
#  can't be precomputed server-side, so this stays as real JS.)

_FIT_SPLIT_JS = """
function fitSplit(W){
  const stage=document.getElementById('stage');
  const sr=stage.getBoundingClientRect(); const sc=sr.width/W;
  const words=[...stage.querySelectorAll('.fit-word')];
  words.forEach(w=>{
    let fs=parseFloat(getComputedStyle(w).fontSize);
    let guard=0;
    while(guard<40){
      const r=w.getBoundingClientRect();
      const left=(r.left-sr.left)/sc, right=(r.right-sr.left)/sc;
      if(left>=54 && right<=W-54) break;
      fs -= 6; if(fs<48) break;
      w.style.fontSize=fs+'px';
      guard++;
    }
  });
}
"""

_BASE_CSS = """
*{margin:0;padding:0;box-sizing:border-box;}
#stage{position:relative;overflow:hidden;background:#000;}
#stage img.bg{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;}
.ov{position:absolute;inset:0;}
.corner{position:absolute;z-index:8;font-family:'Montserrat',sans-serif;font-weight:600;letter-spacing:.2em;opacity:.9;text-transform:uppercase;text-shadow:0 2px 8px rgba(0,0,0,.6);}
.kicker{font-family:'Montserrat',sans-serif;font-weight:700;letter-spacing:.42em;text-transform:uppercase;text-shadow:0 2px 16px rgba(0,0,0,.85);}
.tracks{position:absolute;z-index:8;left:0;right:0;text-align:center;font-family:'Noto Sans KR',sans-serif;font-weight:400;letter-spacing:.02em;opacity:.92;line-height:1.75;text-shadow:0 2px 10px rgba(0,0,0,.8);}
.badge{position:absolute;z-index:8;border-radius:100px;font-family:'Montserrat',sans-serif;font-weight:600;text-transform:uppercase;text-shadow:0 2px 10px rgba(0,0,0,.6);}
.arch svg{overflow:visible;}
"""


def _corners_169(tc: str) -> str:
    return f"""
    <div class="corner" style="top:24px;left:34px;font-size:13px;color:{tc}">Seoul Records<br>&copy;2026</div>
    <div class="corner" style="top:24px;right:34px;font-size:13px;text-align:right;color:{tc}">Present by<br>Seoul Records</div>
    <div class="corner" style="bottom:64px;left:34px;font-size:11px;letter-spacing:.12em;color:{tc}">For every<br>seoul night</div>"""


def _build_169(*, form: str, bg_uri: str, subj_uri: str | None, kicker: str,
               title1: str, title2: str, badge: str, tracks: list[str],
               title_font_css: str, kr_font_css: str, title_color: str,
               point_color: str) -> tuple[str, bool]:
    """Returns (inner_html, needs_fit_split)."""
    W = 1280
    italic, weight = _font_italic_weight(title_font_css)
    fi = "italic" if italic else "normal"
    tsh = "0 8px 34px rgba(0,0,0,.82),0 0 46px rgba(0,0,0,.6)"
    big_style = f"font-family:{title_font_css};font-weight:{weight};font-style:{fi};color:{title_color};text-shadow:{tsh};"
    T1, T2, K, BADGE = _esc(title1), _esc(title2), _esc(kicker), _esc(badge)

    track_lines = _chunk(tracks, 6)
    track_html = (
        f'<div class="tracks" style="bottom:22px;font-size:14px;font-family:{kr_font_css};color:{title_color}">'
        f'{"<br>".join(" / ".join(l) for l in track_lines)}</div>'
    ) if tracks else ""

    inner = f'<img class="bg" src="{bg_uri}">'
    inner += ('<div class="ov" style="background:linear-gradient(180deg,rgba(6,5,12,.5)0%,'
              'rgba(6,5,12,.14)36%,rgba(6,5,12,.2)62%,rgba(6,5,12,.74)100%)"></div>')

    if form == "A" and subj_uri:
        inner += f'<img class="bg" style="z-index:2" src="{subj_uri}">'

    layout = FORMS[form]["layout"]
    needs_fit = False

    if layout in ("split", "split_amp"):
        kick = (f'<div class="kicker" style="position:absolute;z-index:6;top:28px;left:50%;'
                f'transform:translateX(-50%);font-size:22px;color:{point_color}">{K}</div>')
        amp = (f'<div style="position:absolute;z-index:5;left:50%;top:44%;'
               f'transform:translate(-50%,-50%);font-size:70px;{big_style}">&amp;</div>'
               ) if layout == "split_amp" else ""
        inner += kick + (
            '<div style="position:absolute;inset:0;z-index:5;display:flex;justify-content:space-between;'
            f'align-items:center;padding:0 60px;">'
            f'<span class="fit-word" style="font-size:132px;line-height:.95;{big_style}">{T1}</span>'
            f'<span class="fit-word" style="font-size:132px;line-height:.95;{big_style}">{T2}</span></div>'
        ) + amp
        needs_fit = True
    elif layout == "center":
        inner += (
            '<div style="position:absolute;inset:0;z-index:5;display:flex;flex-direction:column;'
            'justify-content:center;align-items:center;text-align:center;">'
            f'<div class="kicker" style="font-size:20px;margin-bottom:16px;color:{point_color}">{K}</div>'
            f'<div style="font-size:120px;line-height:.98;{big_style}">{T1} {T2}</div></div>'
        )
    elif layout == "badge":
        inner += (
            f'<div class="badge" style="top:52px;left:50%;transform:translateX(-50%);border:1.5px solid '
            f'{point_color};padding:9px 30px;font-size:16px;letter-spacing:.34em;color:{point_color}">{BADGE}</div>'
            '<div style="position:absolute;inset:0;z-index:5;display:flex;justify-content:center;'
            'align-items:center;top:6%;">'
            f'<span style="font-size:126px;line-height:.95;{big_style}">{T1} {T2}</span></div>'
        )
    elif layout == "arch":
        inner += (f'<div class="kicker" style="position:absolute;z-index:6;top:30px;left:50%;'
                   f'transform:translateX(-50%);font-size:20px;color:{point_color}">{K}</div>')
        inner += _arch_svg_169(W, f"{T1} {T2}", title_font_css, weight, italic, title_color)

    inner += _corners_169(title_color) + track_html
    return inner, needs_fit


def _build_11(*, form: str, bg_uri: str, subj_uri: str | None, kicker: str,
              title1: str, title2: str, badge: str, tracks: list[str],
              title_font_css: str, kr_font_css: str, title_color: str,
              point_color: str, spine_bg: str, spine_text: str) -> str:
    italic, weight = _font_italic_weight(title_font_css)
    fi = "italic" if italic else "normal"
    tsh = "0 8px 34px rgba(0,0,0,.82),0 0 46px rgba(0,0,0,.6)"
    big_style = f"font-family:{title_font_css};font-weight:{weight};font-style:{fi};color:{title_color};text-shadow:{tsh};"
    T1, T2, K, BADGE = _esc(title1), _esc(title2), _esc(kicker), _esc(badge)

    if form in SPINE_FORMS:
        spine_w = 134
        rows = "".join(
            f'<div style="white-space:nowrap;display:flex;align-items:baseline;gap:6px;">'
            f'<span style="font-family:\'Montserrat\';font-weight:700;font-size:12px;color:{point_color}">{str(i + 1).zfill(2)}</span>'
            f'<span style="font-family:{kr_font_css};font-weight:500;font-size:14px;color:{spine_text}">{_esc(t)}</span></div>'
            for i, t in enumerate(tracks)
        )
        return f"""<div style="position:absolute;inset:0;display:flex;">
      <div style="width:{spine_w}px;height:100%;flex-shrink:0;background:{spine_bg};border-right:1px solid {point_color}55;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px 0;">
        <div style="writing-mode:vertical-rl;text-orientation:mixed;display:flex;flex-shrink:0;">
          <span style="font-family:{title_font_css};font-weight:700;font-size:24px;color:{spine_text};letter-spacing:.1em">SEOUL RECORDS</span>
          <span style="font-family:{title_font_css};font-weight:500;font-style:italic;font-size:16px;color:{point_color};letter-spacing:.08em;margin-top:12px">Vol.01 &middot; {T1} {T2}</span>
        </div>
        <div style="writing-mode:vertical-rl;text-orientation:sideways;display:flex;flex-direction:row;flex-wrap:wrap;align-content:flex-end;gap:13px 8px;margin-top:22px;">{rows}</div>
      </div>
      <div style="flex:1;height:100%;position:relative;overflow:hidden;">
        <img src="{bg_uri}" style="width:100%;height:100%;object-fit:cover;object-position:0% 30%;">
        <div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(8,4,16,.28)0%,transparent 24%,transparent 62%,rgba(8,4,16,.5)100%)"></div>
      </div></div>"""

    # Non-spine forms (C/D/E/F): square full-bleed.
    inner = f'<img class="bg" src="{bg_uri}">'
    inner += ('<div class="ov" style="background:linear-gradient(180deg,rgba(6,5,12,.48)0%,'
              'rgba(6,5,12,.12)34%,rgba(6,5,12,.22)64%,rgba(6,5,12,.72)100%)"></div>')
    layout = FORMS[form]["layout"]
    kick = (f'<div class="kicker" style="position:absolute;z-index:6;top:34px;left:50%;'
            f'transform:translateX(-50%);font-size:19px;color:{point_color}">{K}</div>')

    if layout == "split_amp":
        inner += kick + (
            '<div style="position:absolute;inset:0;z-index:5;display:flex;flex-direction:column;'
            'justify-content:center;align-items:center;gap:6px;">'
            f'<span style="font-size:120px;{big_style}">{T1}</span>'
            f'<span style="font-size:56px;{big_style}">&amp;</span>'
            f'<span style="font-size:120px;{big_style}">{T2}</span></div>'
        )
    elif layout == "badge":
        inner += (
            f'<div class="badge" style="top:60px;left:50%;transform:translateX(-50%);border:1.5px solid '
            f'{point_color};padding:9px 30px;font-size:16px;letter-spacing:.34em;color:{point_color}">{BADGE}</div>'
            '<div style="position:absolute;inset:0;z-index:5;display:flex;flex-direction:column;'
            'justify-content:center;align-items:center;text-align:center;">'
            f'<span style="font-size:118px;line-height:1;{big_style}">{T1}<br>{T2}</span></div>'
        )
    elif layout == "arch":
        inner += kick + _arch_svg_11(f"{T1} {T2}", title_font_css, title_color)
    else:  # split / center → stacked centered pair
        inner += kick + (
            '<div style="position:absolute;inset:0;z-index:5;display:flex;flex-direction:column;'
            'justify-content:center;align-items:center;text-align:center;line-height:.98;">'
            f'<span style="font-size:126px;{big_style}">{T1}</span>'
            f'<span style="font-size:126px;{big_style}">{T2}</span></div>'
        )

    trs = " / ".join(tracks)  # chunk(TR,99) -> one line, matching reference
    inner += (f'<div class="tracks" style="bottom:30px;font-size:13px;font-family:{kr_font_css};'
              f'color:{title_color}">{_esc(trs)}</div>')
    inner += f'<div class="corner" style="top:24px;left:34px;font-size:12px;color:{title_color}">Seoul Records &copy;2026</div>'
    return inner


def _build_html_document(*, form: str, ratio: str, bg_uri: str, subj_uri: str | None,
                         kicker: str, title1: str, title2: str, badge: str,
                         tracks: list[str], title_font_css: str, kr_font_css: str,
                         title_color: str, point_color: str, spine_bg: str,
                         spine_text: str) -> str:
    W, H = _LOGICAL[ratio]
    if ratio == "169":
        inner, needs_fit = _build_169(
            form=form, bg_uri=bg_uri, subj_uri=subj_uri, kicker=kicker,
            title1=title1, title2=title2, badge=badge, tracks=tracks,
            title_font_css=title_font_css, kr_font_css=kr_font_css,
            title_color=title_color, point_color=point_color,
        )
    else:
        inner = _build_11(
            form=form, bg_uri=bg_uri, subj_uri=subj_uri, kicker=kicker,
            title1=title1, title2=title2, badge=badge, tracks=tracks,
            title_font_css=title_font_css, kr_font_css=kr_font_css,
            title_color=title_color, point_color=point_color,
            spine_bg=spine_bg, spine_text=spine_text,
        )
        needs_fit = False

    fit_call = f"fitSplit({W});" if needs_fit else ""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<link href="{GOOGLE_FONTS_HREF}" rel="stylesheet">
<style>{_BASE_CSS}</style>
</head>
<body>
<div id="stage" style="width:{W}px;height:{H}px;">{inner}</div>
<script>
{_FIT_SPLIT_JS}
{fit_call}
</script>
</body>
</html>"""


def _render_stddev(png_path: str) -> float:
    """Sanity check: mean per-channel stddev of the rendered PNG. A near-zero
    value means the page painted blank/black (e.g. the cert-error background
    load failure the spec warns about)."""
    from PIL import ImageStat, Image

    img = Image.open(png_path).convert("RGB")
    stat = ImageStat.Stat(img)
    return sum(stat.stddev) / len(stat.stddev)


def render_thumbnail(
    *,
    form: str,
    ratio: str,
    bg_image_path: str,
    subject_cutout_path: str | None = None,
    kicker: str = "CITYPOP PLAYLIST",
    title1: str = "",
    title2: str = "",
    badge: str = "",
    tracks: list[str] | None = None,
    title_font_css: str | None = None,
    kr_font_css: str | None = None,
    title_color: str = "#f6efe2",
    point_color: str = "#e4be6a",
    spine_bg: str = "#1a1420",
    spine_text: str = "#f4efe4",
    out_path: str,
) -> str:
    """
    Render one (form, ratio) thumbnail via a headless Chromium and save it as
    a PNG at `out_path`. Returns `out_path`.

    title_font_css/kr_font_css default to the form's recommended font when
    not given (recommended_font_css(form) / DEFAULT_KR_FONT_CSS).
    """
    if form not in FORMS:
        raise ValueError(f"Unknown form {form!r} — expected one of {list(FORMS)}")
    if ratio not in _LOGICAL:
        raise ValueError(f"Unknown ratio {ratio!r} — expected '169' or '11'")

    title_font_css = title_font_css or recommended_font_css(form)
    kr_font_css = kr_font_css or DEFAULT_KR_FONT_CSS
    tracks = tracks or []

    bg_uri = _image_data_uri(bg_image_path)
    subj_uri = _cutout_data_uri(subject_cutout_path) if subject_cutout_path else None

    html = _build_html_document(
        form=form, ratio=ratio, bg_uri=bg_uri, subj_uri=subj_uri,
        kicker=kicker, title1=title1, title2=title2, badge=badge, tracks=tracks,
        title_font_css=title_font_css, kr_font_css=kr_font_css,
        title_color=title_color, point_color=point_color,
        spine_bg=spine_bg, spine_text=spine_text,
    )

    logical_w, logical_h = _LOGICAL[ratio]
    target_w, target_h = _TARGET[ratio]
    scale = target_w / logical_w

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(html)
        html_path = tf.name

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        _screenshot(html_path, str(out), logical_w, logical_h, scale)
        if _render_stddev(str(out)) < 20:
            # Sanity-check failure (spec 6): likely a blank/black load
            # failure — retry once.
            _screenshot(html_path, str(out), logical_w, logical_h, scale)
    finally:
        Path(html_path).unlink(missing_ok=True)

    _resize_to_exact(str(out), target_w, target_h)
    return str(out)


def _screenshot(html_path: str, out_path: str, logical_w: int, logical_h: int, scale: float) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--ignore-certificate-errors"])
        try:
            context = browser.new_context(
                ignore_https_errors=True,  # bypass proxy/CDN cert errors — required
                device_scale_factor=scale,
            )
            page = context.new_page()
            page.set_viewport_size({"width": logical_w, "height": logical_h})
            page.goto(f"file://{html_path}")
            # Explicit wait for every <img> to finish loading — skipping this
            # is what produced the "black background, text only" bug.
            page.wait_for_function(
                """() => {
                    const imgs=[...document.querySelectorAll('img')];
                    return imgs.length>0 && imgs.every(i=>i.complete && i.naturalWidth>0);
                }""",
                timeout=30000,
            )
            try:
                page.evaluate("document.fonts.ready")
            except Exception:
                pass
            page.wait_for_timeout(400)  # web-font render settle
            page.screenshot(path=out_path)
        finally:
            browser.close()


def _resize_to_exact(png_path: str, w: int, h: int) -> None:
    """Guard against device_scale_factor rounding drift."""
    from PIL import Image

    img = Image.open(png_path)
    if img.size != (w, h):
        img = img.resize((w, h), Image.LANCZOS)
        img.save(png_path)
