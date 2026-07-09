"""Render the ai-readiness score JSON into a clean single-file HTML dashboard
(Inter + JetBrains Mono, light, SVG/CSS bars — no fantasy). Usage:
  python score_to_html.py <score.json> <out.html>
"""
import json, sys, datetime, subprocess

src = sys.argv[1] if len(sys.argv) > 1 else ".claude/ai-readiness-score.json"
out = sys.argv[2] if len(sys.argv) > 2 else ".claude/ai-readiness-map.html"
d = json.load(open(src, encoding="utf-8"))
cats = d.get("categories", {})
total, grade, gc = d.get("total"), d.get("grade"), d.get("grade_color", "amber")
meta = d.get("meta", {})
actions = d.get("actions", [])[:6]
extras = d.get("extras", {})
large = extras.get("large_files") or d.get("large_files") or []
try:
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip()
except Exception:
    branch = "main"
today = datetime.date.today().isoformat()
COL = {"green": "#22a06b", "amber": "#d99000", "red": "#d64545"}


def barcol(s, m):
    r = s / m if m else 0
    return COL["green"] if r >= 0.75 else COL["amber"] if r >= 0.5 else COL["red"]


rows = ""
for k in ["A", "B", "C", "D", "E", "F", "G"]:
    c = cats.get(k) or {}
    s, m, nm = c.get("score", 0), c.get("max", 1), c.get("name", k)
    w = round((s / m * 100) if m else 0, 1)
    ev = (c.get("findings") or [""])[0]
    ev = (ev[:96] + "…") if len(ev) > 96 else ev
    rows += (f'<div class="row"><div class="rl"><span class="tag">{k}</span> {nm}</div>'
             f'<div class="track"><div class="fill" style="width:{w}%;background:{barcol(s,m)}"></div></div>'
             f'<div class="rs">{s}/{m}</div></div><div class="sub">{ev}</div>')
act = ""
for a in actions:
    act += (f'<div class="act"><span class="tag">{a.get("category","")}</span>'
            f'<span class="eff">{a.get("effort","")}</span> {a.get("action","")}'
            f'<div class="imp">{a.get("impact","")}</div></div>')
lg = ""
for f in large[:8]:
    if isinstance(f, dict):
        nm, ln = f.get("path"), f.get("lines")
    elif isinstance(f, (list, tuple)):
        nm, ln = f[0], (f[1] if len(f) > 1 else "")
    else:
        nm, ln = f, ""
    lg += f'<div class="lf"><code>{nm}</code><b>{ln}</b></div>'
gcol = COL.get(gc, "#d99000")

html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>AI-Readiness · Seoul Records Production OS</title><style>
*{{box-sizing:border-box;margin:0}}
body{{font-family:Inter,system-ui,'Segoe UI',sans-serif;background:#fafafa;color:#1a1a1a;padding:32px;line-height:1.5}}
.mono{{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace}}
.wrap{{max-width:960px;margin:0 auto}} h1{{font-size:20px}} .meta{{color:#6b7280;font-size:12px;margin:4px 0 24px}}
.hero{{display:flex;align-items:center;gap:24px;background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:24px;margin-bottom:20px}}
.num{{font-size:56px;font-weight:800;font-family:'JetBrains Mono',monospace;line-height:1}} .num small{{font-size:20px;color:#6b7280}}
.badge{{display:inline-block;padding:6px 14px;border-radius:999px;color:#fff;font-weight:700;font-size:13px;background:{gcol}}}
.desc{{color:#6b7280;font-size:13px;margin-top:8px;max-width:440px}}
.stats{{margin-left:auto;display:flex;gap:20px;text-align:center}} .stat b{{display:block;font-size:22px;font-family:'JetBrains Mono',monospace}} .stat span{{font-size:11px;color:#6b7280}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:20px;margin-bottom:20px}}
.card h2{{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;margin-bottom:12px}}
.row{{display:flex;align-items:center;gap:12px;margin-top:12px}} .rl{{width:240px;font-size:13px;font-weight:600}}
.tag{{display:inline-block;background:#eef1f4;color:#374151;border-radius:5px;padding:1px 6px;font-size:11px;font-weight:700;font-family:'JetBrains Mono',monospace}}
.track{{flex:1;height:9px;background:#eef1f4;border-radius:5px;overflow:hidden}} .fill{{height:100%;border-radius:5px}}
.rs{{width:46px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600}}
.sub{{margin:2px 0 0 252px;color:#6b7280;font-size:11px}}
.act{{border-top:1px solid #e5e7eb;padding:10px 0;font-size:13px}} .act:first-child{{border-top:0}}
.eff{{color:#6b7280;font-family:'JetBrains Mono',monospace;font-size:11px;margin:0 6px}} .imp{{color:#6b7280;font-size:11px;margin-top:2px}}
.lf{{display:flex;justify-content:space-between;font-size:12px;padding:5px 0;border-top:1px dashed #e5e7eb}} .lf code{{font-family:'JetBrains Mono',monospace}}
.foot{{color:#6b7280;font-size:11px;text-align:center;margin-top:24px}}
</style></head><body><div class="wrap">
<h1>AI-Readiness · Seoul Records Production OS</h1>
<div class="meta mono">{today} · branch {branch} · modules {meta.get('modules_total','?')} · context files {meta.get('context_files_total','?')}</div>
<div class="hero"><div><div class="num">{total}<small>/100</small></div>
<div style="margin-top:10px"><span class="badge">{grade}</span></div>
<div class="desc">최약점: Navigation(A) · Tribal Knowledge(C) · Agent Outcomes(G) — 팀·모노레포용 인프라 항목. 강점: Dependency map(D) · Verification(E).</div></div>
<div class="stats"><div class="stat"><b>{meta.get('modules_total','?')}</b><span>modules</span></div>
<div class="stat"><b>{meta.get('context_files_total','?')}</b><span>context files</span></div>
<div class="stat"><b>{len(large)}</b><span>files &gt;300L</span></div></div></div>
<div class="card"><h2>7-Category Score (v2 rubric · 100pt)</h2>{rows}</div>
<div class="card"><h2>Top ROI Actions</h2>{act}</div>
<div class="card"><h2>Large Files (&gt;300 lines · split candidates)</h2>{lg}</div>
<div class="foot mono">Seoul Records Production OS · AI-Readiness v2 · scored {today}</div>
</div></body></html>"""
open(out, "w", encoding="utf-8").write(html)
print(f"dashboard written: {len(html)} bytes -> {out} (total {total} {grade})")
