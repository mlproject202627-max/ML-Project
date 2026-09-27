#!/usr/bin/env python3
"""
Generator for Insider-Threat-Detection-System.pptx  (10 slides)

Premium light/creamy deck, built from the Python standard library only
(no python-pptx, no virtualenv). Every technical claim, dataset statistic
and model metric in this deck is read from the project itself:

  backend/ml/generate_dataset.py          NUM_SAMPLES=10000, THREAT_RATIO=0.08, SEED=42
  backend/ml/artifacts/*.csv              10,000 raw rows x 26 columns, 8.0% threat rate,
                                          8,000 / 2,000 train-test rows
  backend/ml/preprocess.py                20 numeric + 3 categorical features -> 42 columns
  backend/ml/train.py                     LogisticRegression + RandomForest, best-F1 select
  backend/ml/artifacts/model_metrics.json sentinel-ueba-v1
  backend/ml/risk_engine.py               weights 0.40 / 0.30 / 0.15 / 0.15, bands 40/70/90
  backend/ml/rules.py                     8 deterministic rules

Run:  python3 make_insider_deck.py
"""
import os
import zipfile
from xml.sax.saxutils import escape as esc

OUT = "Insider-Threat-Detection-System.pptx"
NSLIDES = 10

# ── Palette: warm ivory, cream, soft beige ──────────────────────────────────
BG        = "F6EDDD"   # warm cream canvas
BG_TOP    = "FFFDF8"   # near-white top stop
CARD      = "FFFFFF"
CARD_2    = "FDF8EC"   # cream tint
CARD_HI   = "FBF4E4"   # deeper beige chip
LINE      = "E8DDC8"
LINE_HI   = "D8C7A6"
ACCENT    = "0E7490"   # restrained deep teal
ACCENT_2  = "C2410C"   # burnt rust, used sparingly
TXT       = "1F1A14"   # charcoal ink
TXT_2     = "63553F"
TXT_3     = "7C6A4E"
GHOST     = "EBDFC8"
CRIT      = "9F1239"
WARN      = "8A5406"
OK        = "166534"

# ── Geometry (16:9, EMU) ────────────────────────────────────────────────────
SLIDE_W, SLIDE_H = 12192000, 6858000
MX, CW = 838200, 12192000 - 2 * 838200
BODY_Y   = 1800000     # top of the content band
BODY_END = 5920000     # content must not pass this line
FOOT_Y   = 6200000

NS = (
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
)
PKG_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


# ── XML helpers ─────────────────────────────────────────────────────────────
def run(text, color=TXT_2, sz=1150, b=0, italic=0, font="Inter", spc=None):
    sp = f' spc="{spc}"' if spc else ""
    return (
        f'<a:r><a:rPr lang="en-US" sz="{sz}" b="{b}" i="{italic}"{sp} dirty="0">'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="{font}"/><a:cs typeface="{font}"/>'
        f'</a:rPr><a:t>{esc(text)}</a:t></a:r>'
    )


def para(runs, algn="l", before=0, line=None, after=0):
    ppr = f'<a:pPr algn="{algn}">'
    if line is not None:
        ppr += f'<a:lnSpc><a:spcPct val="{line}"/></a:lnSpc>'
    if before:
        ppr += f'<a:spcBef><a:spcPts val="{before}"/></a:spcBef>'
    if after:
        ppr += f'<a:spcAft><a:spcPts val="{after}"/></a:spcAft>'
    ppr += "</a:pPr>"
    return f'<a:p>{ppr}{"".join(runs)}</a:p>'


def bullet(text, color=TXT_2, sz=1150, marker="\u2013", before=430, mcolor=ACCENT_2):
    return para([run(marker + "   ", color=mcolor, sz=sz, b=1), run(text, color=color, sz=sz)],
                before=before)


def label(text, color=TXT_3, sz=950, before=0):
    """Small all-caps kicker."""
    return para([run(text.upper(), color=color, sz=sz, b=1, spc=80)], before=before)


def textbox(sid, x, y, cx, cy, paras, anchor="t"):
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="TextBox {sid}"/>'
        f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
        f'<p:txBody><a:bodyPr wrap="square" rtlCol="0" anchor="{anchor}">'
        f'<a:normAutofit/></a:bodyPr><a:lstStyle/>{"".join(paras)}</p:txBody></p:sp>'
    )


def fill_xml(fill, fill2=None, alpha=None, angle=5400000):
    if fill2:
        return (
            f'<a:gradFill><a:gsLst>'
            f'<a:gs pos="0"><a:srgbClr val="{fill}"/></a:gs>'
            f'<a:gs pos="100000"><a:srgbClr val="{fill2}"/></a:gs>'
            f'</a:gsLst><a:lin ang="{angle}" scaled="1"/></a:gradFill>'
        )
    if alpha is not None:
        return f'<a:solidFill><a:srgbClr val="{fill}"><a:alpha val="{alpha}"/></a:srgbClr></a:solidFill>'
    return f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'


SHADOW = (
    '<a:effectLst><a:outerShdw blurRad="120000" dist="26000" dir="5400000" '
    'rotWithShape="0"><a:srgbClr val="8A7350"><a:alpha val="16000"/></a:srgbClr>'
    "</a:outerShdw></a:effectLst>"
)


def shape(sid, x, y, cx, cy, fill=CARD, paras=None, prst="roundRect", line_color=None,
          anchor="t", pad=150000, alpha=None, fill2=None, grad_ang=5400000,
          line_w=9525, shadow=None, dash=None):
    if dash and line_color:
        ln = (f'<a:ln w="{line_w}"><a:solidFill><a:srgbClr val="{line_color}"/></a:solidFill>'
              f'<a:prstDash val="{dash}"/></a:ln>')
    elif line_color:
        ln = f'<a:ln w="{line_w}"><a:solidFill><a:srgbClr val="{line_color}"/></a:solidFill></a:ln>'
    else:
        ln = "<a:ln><a:noFill/></a:ln>"
    fx = SHADOW if (shadow is True or (shadow is None and prst == "roundRect")) else ""
    body = "".join(paras) if paras else '<a:p><a:endParaRPr lang="en-US"/></a:p>'
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="Shape {sid}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="{prst}"><a:avLst/></a:prstGeom>'
        f'{fill_xml(fill, fill2, alpha, grad_ang)}{ln}{fx}</p:spPr>'
        f'<p:txBody><a:bodyPr wrap="square" rtlCol="0" anchor="{anchor}" '
        f'lIns="{pad}" tIns="{pad // 2}" rIns="{pad}" bIns="{pad // 2}"><a:normAutofit/></a:bodyPr>'
        f'<a:lstStyle/>{body}</p:txBody></p:sp>'
    )


def glow(sid, x, y, size, color=ACCENT, alpha=9000):
    return shape(sid, x, y, size, size, fill=color, alpha=alpha, prst="ellipse", shadow=False)


def card(sid, x, y, w, h, kicker, body, border=LINE, tint=CARD, pad=170000, anchor="t"):
    paras = [label(kicker, color=ACCENT if border == ACCENT else TXT_3)]
    paras += body
    return shape(sid, x, y, w, h, fill=tint, line_color=border, anchor=anchor, pad=pad, paras=paras)


def slide_xml(shapes):
    tree = (
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
    )
    bg = (
        f'<p:bg><p:bgPr><a:gradFill rotWithShape="1"><a:gsLst>'
        f'<a:gs pos="0"><a:srgbClr val="{BG_TOP}"/></a:gs>'
        f'<a:gs pos="100000"><a:srgbClr val="{BG}"/></a:gs>'
        f'</a:gsLst><a:lin ang="2700000" scaled="1"/></a:gradFill>'
        f"<a:effectLst/></p:bgPr></p:bg>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f"<p:sld {NS}><p:cSld>{bg}"
        f"<p:spTree>{tree}{''.join(shapes)}</p:spTree>"
        f"</p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )


def chrome(eyebrow, title, page, title_sz=2650):
    """Shared header (accent bar, eyebrow, title, rule, ghost numeral) and footer."""
    return [
        glow(11, SLIDE_W - 3400000, -1500000, 4200000, ACCENT, 9000),
        glow(12, -1500000, SLIDE_H - 1900000, 3200000, ACCENT_2, 6000),
        shape(13, 0, 0, SLIDE_W, 26000, fill=ACCENT, fill2=ACCENT_2, prst="rect",
              grad_ang=0, shadow=False),
        textbox(14, SLIDE_W - MX - 1700000, 400000, 1700000, 950000, [
            para([run(f"{page:02d}", color=GHOST, sz=5200, b=1)], algn="r", before=0)
        ]),
        textbox(15, MX, 600000, CW, 250000, [label(eyebrow)]),
        textbox(16, MX, 860000, CW, 600000, [
            para([run(title, color=TXT, sz=title_sz, b=1)], before=0)
        ]),
        shape(17, MX, 1530000, 600000, 28000, fill=ACCENT, fill2=ACCENT_2, prst="rect",
              grad_ang=0, shadow=False),
        textbox(18, MX, FOOT_Y, 7400000, 260000, [
            para([run("Insider Threat Detection System  \u00b7  AI-Powered Behavioral Analytics "
                      "for Enterprise Security", color=TXT_3, sz=850)], before=0)
        ]),
        textbox(19, SLIDE_W - MX - 900000, FOOT_Y, 900000, 260000, [
            para([run(f"{page} / {NSLIDES}", color=TXT_3, sz=850)], algn="r", before=0)
        ]),
    ]


def flow(sid, nodes, x, y, w, h, gap=200000, arrow="\u2192", node_fill=CARD,
         node_line=LINE, sz=1000, tc=TXT):
    """Horizontal process chain: chip → chip → chip. Returns (shapes, total_width)."""
    n = len(nodes)
    bw = (w - (n - 1) * gap) // n
    out = []
    for i, node in enumerate(nodes):
        nx = x + i * (bw + gap)
        out.append(shape(sid + i, nx, y, bw, h, fill=node_fill, line_color=node_line,
                         anchor="ctr", pad=90000, paras=[
            para([run(node, color=tc, sz=sz, b=1)], algn="ctr", before=0)
        ]))
        if i < n - 1:
            out.append(textbox(sid + 40 + i, nx + bw, y, gap, h, [
                para([run(arrow, color=ACCENT, sz=1300, b=1)], algn="ctr", before=0)
            ], anchor="ctr"))
    return out


def vchain(sid, items, x, y, w, row_h=380000, gap=80000, sz=1100, fill=CARD):
    """Vertical chain of labelled rows joined by down arrows."""
    out, cy = [], y
    for i, (head, sub) in enumerate(items):
        out.append(shape(sid + i, x, cy, w, row_h, fill=fill, line_color=LINE,
                         anchor="ctr", pad=120000, prst="roundRect", paras=[
            para([run(head + "   ", color=TXT, sz=sz, b=1),
                  run(sub, color=TXT_2, sz=sz - 60)], before=0)
        ]))
        cy += row_h
        if i < len(items) - 1:
            out.append(textbox(sid + 30 + i, x, cy, w, gap, [
                para([run("\u2193", color=ACCENT, sz=1200, b=1)], algn="ctr", before=0)
            ], anchor="ctr"))
            cy += gap
    return out


slides = []

# ═══════════════════════════════ SLIDE 1 — Title / project identity ═════════
s1 = [
    glow(11, SLIDE_W - 3800000, -1800000, 5000000, ACCENT, 12000),
    glow(12, -2000000, SLIDE_H - 2600000, 4400000, ACCENT_2, 8000),
    shape(13, 0, 0, SLIDE_W, 30000, fill=ACCENT, fill2=ACCENT_2, prst="rect",
          grad_ang=0, shadow=False),
    textbox(14, MX, 1230000, CW, 260000, [label("College Project  \u00b7  Cybersecurity & AI", sz=1000)]),
    textbox(15, MX, 1500000, CW, 900000, [
        para([run("Insider Threat Detection System", color=TXT, sz=4200, b=1)], before=0)
    ]),
    textbox(16, MX, 2420000, CW, 400000, [
        para([run("AI-Powered Behavioral Analytics for Enterprise Security",
                  color=ACCENT, sz=1700, b=1)], before=0)
    ]),
    shape(17, MX, 2900000, 900000, 30000, fill=ACCENT, fill2=ACCENT_2, prst="rect",
          grad_ang=0, shadow=False),
]
s1 += flow(20, ["Employee Activity", "Behavioral Analysis", "Machine Learning", "Security Alert"],
           MX, 3100000, CW, 780000, gap=260000, sz=1150)

meta = [("Team", "[ Team Name ]"),
        ("Members", "[ Member 1 \u00b7 Member 2 \u00b7 Member 3 ]"),
        ("Institution", "[ College / University ]"),
        ("Department", "[ Computer Science & Engineering ]")]
mw = (CW - 3 * 160000) // 4
for i, (k, v) in enumerate(meta):
    s1.append(shape(40 + i, MX + i * (mw + 160000), 4180000, mw, 900000, fill=CARD_HI,
                    line_color=LINE_HI, anchor="ctr", pad=120000, paras=[
        para([run(k.upper(), color=TXT_3, sz=900, b=1)], algn="ctr", before=0),
        para([run(v, color=TXT, sz=1000, b=1)], algn="ctr", before=280),
    ]))
s1 += [
    textbox(50, MX, 5300000, CW, 480000, [
        para([run("Built with   ", color=TXT_3, sz=950),
              run("React 19  \u00b7  TypeScript  \u00b7  Vite  \u00b7  Tailwind v4  \u00b7  Recharts",
                  color=TXT_2, sz=950, b=1)], before=0),
        para([run("Serving stack   ", color=TXT_3, sz=950),
              run("FastAPI  \u00b7  SQLAlchemy 2  \u00b7  PostgreSQL  \u00b7  Alembic  \u00b7  Pydantic v2  "
                  "\u00b7  JWT + RBAC", color=TXT_2, sz=950, b=1)], before=300),
        para([run("Intelligence   ", color=TXT_3, sz=950),
              run("scikit-learn  \u00b7  pandas  \u00b7  NumPy  \u00b7  joblib", color=TXT_2, sz=950, b=1)],
             before=300),
    ]),
    textbox(51, MX, FOOT_Y, 7400000, 260000, [
        para([run("Insider Threat Detection System  \u00b7  all identities, events and detections "
                  "are synthetic sample data", color=TXT_3, sz=850)], before=0)
    ]),
    textbox(52, SLIDE_W - MX - 900000, FOOT_Y, 900000, 260000, [
        para([run("1 / 10", color=TXT_3, sz=850)], algn="r", before=0)
    ]),
]
slides.append(slide_xml(s1))

# ═══════════════════════════════ SLIDE 2 — Problem statement ════════════════
s2 = chrome("The Challenge", "Why Insider Threats Are Hard to Detect", 2)
hard = [
    ("Authorized access", "Insiders hold valid credentials \u2014 no perimeter is crossed."),
    ("Privilege abuse", "Permissions granted for the job can reach sensitive data."),
    ("Compromised accounts", "A hijacked account behaves like its owner for a while."),
    ("Gradual exfiltration", "Theft spread over weeks stays under per-event thresholds."),
    ("Alert flooding", "Static rules fire on rare-but-legitimate events, not real intent."),
    ("Manual review", "No team can hand-baseline thousands of identities."),
]
left = [label("WHY DETECTION FAILS", color=ACCENT)]
for h, d in hard:
    left.append(para([run(h + "  \u2014  ", color=TXT, sz=1130, b=1),
                      run(d, color=TXT_2, sz=1130)], before=300, line=100000))
s2.append(shape(20, MX, BODY_Y, 5100000, 2760000, fill=CARD, line_color=ACCENT,
                anchor="t", pad=170000, paras=left))

normal = [("Sign-in window", "09:15 \u00b1 45 min"), ("Sensitive files / day", "1\u20133"),
          ("Data leaving the org", "2\u20135 MB"), ("Peer deviation", "within baseline")]
susp = [("Sign-in window", "03:41, 4 of 5 days"), ("Sensitive files / day", "27"),
        ("Data leaving the org", "412 MB"), ("Peer deviation", "+3.8 \u03c3")]
s2.append(shape(21, MX + 5300000, BODY_Y, CW - 5300000, 1310000, fill=CARD,
                line_color=OK, anchor="t", pad=160000, paras=
                [para([run("NORMAL USER", color=OK, sz=1000, b=1),
                       run("      consistent with baseline + peer group", color=TXT_3, sz=930)],
                      before=0)] +
                [para([run(k + "   ", color=TXT_2, sz=1000), run(v, color=TXT, sz=1000, b=1)],
                      before=165) for k, v in normal]))
s2.append(shape(22, MX + 5300000, 3250000, CW - 5300000, 1310000, fill=CARD,
                line_color=CRIT, anchor="t", pad=160000, paras=
                [para([run("SUSPICIOUS USER", color=CRIT, sz=1000, b=1),
                       run("      deviates on 4 signals at once", color=TXT_3, sz=930)], before=0)] +
                [para([run(k + "   ", color=TXT_2, sz=1000), run(v, color=TXT, sz=1000, b=1)],
                      before=165) for k, v in susp]))
s2.append(shape(23, MX, 4720000, CW, 900000, fill=CARD_2, line_color=ACCENT, anchor="ctr",
                pad=200000, paras=[
    para([run("How can an organization distinguish ", color=TXT_2, sz=1450),
          run("legitimate employee behavior", color=OK, sz=1450, b=1),
          run(" from ", color=TXT_2, sz=1450),
          run("potentially dangerous behavioral deviations", color=CRIT, sz=1450, b=1),
          run("?", color=TXT_2, sz=1450)], algn="ctr", before=0),
]))
slides.append(slide_xml(s2))

# ═══════════════════════════════ SLIDE 3 — Threat landscape ════════════════
s3 = chrome("Threat Model", "The Three Insider Threat Categories", 3)
cats = [
    ("01", "Malicious Insider", ACCENT,
     "A trusted employee who deliberately steals data, sabotages systems or sells access.",
     "Example: bulk download of finance records at 03:00, then upload to personal cloud.",
     "Impact: data breach, fraud, IP loss, regulatory penalties."),
    ("02", "Negligent Insider", WARN,
     "An employee who weakens security through carelessness rather than intent.",
     "Example: disabling endpoint protection, sharing credentials, USB use for work files.",
     "Impact: exposure of sensitive data, malware entry, audit failures."),
    ("03", "Compromised Account", CRIT,
     "An attacker operating a real user's session, so activity looks partly legitimate.",
     "Example: impossible travel, new-device sign-in, then resource sweeping and lateral moves.",
     "Impact: privilege escalation, persistent access, large-scale exfiltration."),
]
cw3 = (CW - 2 * 160000) // 3
for i, (num, name, col, desc, ex, imp) in enumerate(cats):
    s3.append(shape(20 + i, MX + i * (cw3 + 160000), BODY_Y, cw3, 1900000, fill=CARD,
                    line_color=col, anchor="t", pad=170000, paras=[
        para([run(num + "   ", color=col, sz=1150, b=1),
              run(name, color=TXT, sz=1350, b=1)], before=0),
        para([run(desc, color=TXT_2, sz=1050)], before=380, line=104000),
        para([run(ex, color=TXT_3, sz=1000)], before=330, line=104000),
        para([run(imp, color=TXT_2, sz=1000, b=1)], before=330, line=104000),
    ]))
s3.append(textbox(30, MX, 3900000, CW, 240000, [label("BEHAVIORAL DETECTION FLOW")]))
s3 += flow(31, ["Normal Behavior", "Behavioral Baseline", "Behavioral Deviation",
                "Risk Score", "Security Alert"], MX, 4160000, CW, 820000, gap=200000, sz=1000)
s3.append(textbox(38, MX, 5080000, CW, 700000, [
    para([run("The baseline is per-identity and per-peer-group. A deviation is only meaningful "
              "relative to ", color=TXT_2, sz=1120),
          run("what this user \u2014 and their peers \u2014 normally do", color=TXT, sz=1120, b=1),
          run(". That is why the system scores behavior instead of counting events.",
              color=TXT_2, sz=1120)], before=0, line=108000),
]))
slides.append(slide_xml(s3))

# ═══════════════════════════════ SLIDE 4 — Proposed solution ════════════════
s4 = chrome("The Solution", "AI-Based Insider Threat Detection", 4)
s4 += flow(20, ["User Activity", "Data Collection", "Preprocessing", "Feature Engineering",
                "Machine Learning"], MX, BODY_Y, CW, 900000, gap=180000, sz=1000)
s4 += flow(26, ["Behavioral Analysis", "Risk Scoring", "Alert Generation", "Security Dashboard"],
           MX, 2880000, CW, 900000, gap=180000, sz=1050, node_fill=CARD_HI)
comps = [
    ("Collection & features", "Behavioural windows are aggregated per identity and reduced to 23 "
     "raw features covering timing, volume, privilege and data movement."),
    ("Machine learning", "Two classifiers are trained on the same preprocessed matrix; the better "
     "F1 score is promoted to the serving artifact."),
    ("Analysis & scoring", "Probability is combined with behavioural, asset and privilege context "
     "into a 0\u2013100 score banded LOW \u2192 CRITICAL."),
    ("Alerts & dashboard", "Eight deterministic rules name the behaviour, and the analyst sees "
     "queue, timeline, model insights and policies."),
]
cw4 = (CW - 3 * 150000) // 4
for i, (h, d) in enumerate(comps):
    s4.append(shape(30 + i, MX + i * (cw4 + 150000), 3960000, cw4, 1320000, fill=CARD,
                    line_color=LINE, anchor="t", pad=150000, paras=[
        label(f"{i + 1} \u00b7 {h}", color=ACCENT),
        para([run(d, color=TXT_2, sz=980)], before=280, line=102000),
    ]))
s4.append(shape(35, MX, 5380000, CW, 540000, fill=CARD_2, line_color=ACCENT_2, anchor="ctr",
                pad=180000, paras=[
    para([run("Behavioral patterns, not just access permissions: ", color=TXT, sz=1150, b=1),
          run("two users with identical entitlements receive different risk scores, because the "
              "score reflects what they do with those entitlements.", color=TXT_2, sz=1150)],
         algn="ctr", before=0)]))
slides.append(slide_xml(s4))

# ═══════════════════════════════ SLIDE 5 — Dataset & features ═══════════════
s5 = chrome("Data Foundation", "Dataset & Feature Engineering", 5)
s5.append(shape(20, MX, BODY_Y, 5100000, 1900000, fill=CARD, line_color=ACCENT,
                anchor="t", pad=170000, paras=[
    label("THE DATASET", color=ACCENT),
    para([run("sentinel_ueba_synthetic_raw.csv", color=TXT, sz=1150, b=1)], before=300),
    para([run("Purpose-built synthetic behavioural dataset \u2014 generated by the project "
              "itself, so no real security telemetry is involved.", color=TXT_2, sz=1000)],
         before=260, line=102000),
    para([run("10,000", color=TXT, sz=1050, b=1), run(" behavioural windows      ", color=TXT_2, sz=1000),
          run("26", color=TXT, sz=1050, b=1), run(" columns      ", color=TXT_2, sz=1000),
          run("8.0%", color=TXT, sz=1050, b=1), run(" threat rate", color=TXT_2, sz=1000)],
         before=300),
    para([run("800", color=TXT, sz=1050, b=1), run(" threat windows / ", color=TXT_2, sz=1000),
          run("9,200", color=TXT, sz=1050, b=1), run(" normal      ", color=TXT_2, sz=1000),
          run("seed 42", color=TXT, sz=1050, b=1)], before=220),
    para([run("Split   ", color=TXT_3, sz=1000),
          run("8,000 train / 2,000 test", color=TXT, sz=1000, b=1),
          run("      Label   ", color=TXT_3, sz=1000),
          run("insider_threat  (0 / 1)", color=TXT, sz=1000, b=1)], before=220),
]))
s5.append(shape(21, MX + 5300000, BODY_Y, CW - 5300000, 1900000, fill=CARD, line_color=LINE,
                anchor="t", pad=160000, paras=
                [label("RAW LOGS \u2192 MODEL-READY DATA", color=ACCENT)] +
                [para([run(f"{i + 1}   ", color=ACCENT, sz=1000, b=1),
                       run(n, color=TXT, sz=1050, b=1),
                       run("   " + d, color=TXT_3, sz=950)], before=200) for i, (n, d) in enumerate([
                    ("Data cleaning", "median imputation for gaps, schema + duplicate-id checks"),
                    ("Feature extraction", "20 numeric + 3 categorical behavioural features"),
                    ("Normalization", "log1p on 8 skewed features, then standard scaling"),
                    ("Encoding", "one-hot for department, role, account_type")])]))
s5.append(textbox(26, MX, 3840000, CW, 240000, [
    label("FEATURE FAMILIES \u2014 23 RAW FEATURES BECOME 42 MODEL COLUMNS")]))
fams = [
    ("Authentication", "login_count_7d \u00b7 failed_login_rate \u00b7 session_duration_mean_min"),
    ("Timing / off-hours", "off_hours_ratio \u00b7 weekend_ratio \u00b7 after_hours_sensitive_access"),
    ("Data access", "sensitive_file_access \u00b7 asset_criticality"),
    ("Exfiltration", "external_transfer_mb \u00b7 cloud_upload_mb \u00b7 email_external_ratio"),
    ("Device / endpoint", "usb_event_count \u00b7 new_device_score \u00b7 remote_session_ratio"),
    ("Network / location", "unusual_location_score \u00b7 access_velocity_per_hour"),
    ("Privilege", "privileged_access_count \u00b7 privilege_change_count_30d"),
    ("Baseline context", "peer_deviation_score \u00b7 dormant_account_days"),
    ("Identity (categorical)", "department \u00b7 role \u00b7 account_type  \u2192  one-hot encoded"),
]
fw3 = (CW - 2 * 150000) // 3
for i, (h, d) in enumerate(fams):
    col, row = i % 3, i // 3
    s5.append(shape(30 + i, MX + col * (fw3 + 150000), 4100000 + row * 500000, fw3, 440000,
                    fill=CARD_HI, line_color=LINE, anchor="ctr", pad=110000, paras=[
        para([run(h, color=TXT, sz=1000, b=1)], before=0),
        para([run(d, color=TXT_3, sz=900)], before=170, line=98000),
    ]))
slides.append(slide_xml(s5))

# ═══════════════════════════════ SLIDE 6 — ML pipeline ══════════════════════
s6 = chrome("Machine Learning", "Model Pipeline, Algorithms & Evaluation", 6)
stages = [
    ("Dataset", "10,000 windows, 8% threat rate"),
    ("Preprocessing", "impute \u2192 log1p \u2192 scale \u2192 one-hot"),
    ("Feature engineering", "20 numeric + 3 categorical \u2192 42 columns"),
    ("Train / test split", "8,000 / 2,000 stratified"),
    ("Model training", "class_weight=\"balanced\""),
    ("Validation", "precision, recall, F1, ROC-AUC, PR-AUC"),
    ("Prediction", "threat probability per behavioural window"),
    ("Risk classification", "LOW / MEDIUM / HIGH / CRITICAL"),
]
paras6 = [label("TRAINING PIPELINE", color=ACCENT)]
for i, (n, d) in enumerate(stages):
    paras6.append(para([run(f"{i + 1:02d}   ", color=ACCENT, sz=1000, b=1),
                        run(n, color=TXT, sz=1050, b=1)], before=250))
    paras6.append(para([run(d, color=TXT_3, sz=900)], before=60))
s6.append(shape(20, MX, BODY_Y, 4300000, 2980000, fill=CARD, line_color=ACCENT,
                anchor="t", pad=150000, paras=paras6))
s6.append(shape(21, MX + 4500000, BODY_Y, CW - 4500000, 1420000, fill=CARD, line_color=LINE,
                anchor="t", pad=160000, paras=[
    label("ALGORITHMS IMPLEMENTED", color=ACCENT),
    para([run("Logistic Regression", color=TXT, sz=1150, b=1),
          run("   class_weight=\"balanced\", max_iter=1000, seed 42", color=TXT_2, sz=1000)],
         before=320),
    para([run("Random Forest", color=TXT, sz=1150, b=1),
          run("   n_estimators=200, max_depth=10, class_weight=\"balanced\"", color=TXT_2, sz=1000)],
         before=280),
    para([run("Both are trained on the identical preprocessed matrix; the higher F1 is saved. "
              "Saved artifact: sentinel-ueba-v1 \u2014 Logistic Regression.",
              color=TXT_3, sz=980)], before=340, line=102000),
]))
s6.append(shape(22, MX + 4500000, 3400000, CW - 4500000, 1400000, fill=CARD, line_color=LINE,
                anchor="t", pad=160000, paras=[
    label("PREDICTION OUTPUT", color=ACCENT),
    para([run("Model probability \u2192 binary call at 0.5, then contextual scoring bands:",
              color=TXT_2, sz=1000)], before=300, line=102000),
    para([run("LOW  ", color=OK, sz=1050, b=1), run("0\u201339      ", color=TXT_2, sz=1000),
          run("MEDIUM  ", color=WARN, sz=1050, b=1), run("40\u201369      ", color=TXT_2, sz=1000),
          run("HIGH  ", color=ACCENT_2, sz=1050, b=1), run("70\u201389      ", color=TXT_2, sz=1000),
          run("CRITICAL  ", color=CRIT, sz=1050, b=1), run("90\u2013100", color=TXT_2, sz=1000)],
         before=320),
]))
metrics = [("Precision", "1.0000"), ("Recall", "1.0000"), ("F1", "1.0000"),
           ("ROC-AUC", "1.0000"), ("PR-AUC", "1.0000"), ("FPR", "0.0000"),
           ("Accuracy", "1.0000")]
mw6 = (CW - 6 * 110000) // 7
for i, (k, v) in enumerate(metrics):
    s6.append(shape(30 + i, MX + i * (mw6 + 110000), 4900000, mw6, 560000, fill=CARD_HI,
                    line_color=LINE_HI, anchor="ctr", pad=80000, paras=[
        para([run(k.upper(), color=TXT_3, sz=850, b=1)], algn="ctr", before=0),
        para([run(v, color=TXT, sz=1400, b=1)], algn="ctr", before=140),
    ]))
s6.append(textbox(38, MX, 5520000, CW, 460000, [
    para([run("Measured on the 2,000-window synthetic holdout \u2014 confusion matrix "
              "1,839 TN / 0 FP / 0 FN / 161 TP. ", color=TXT_2, sz=980),
          run("Perfect scores are expected here: the generator produces two cleanly separable "
              "distributions, so these are not real-world guarantees. Honest evaluation needs a "
              "labelled real corpus or injected red-team activity.", color=TXT_3, sz=980)],
         before=0, line=102000),
]))
slides.append(slide_xml(s6))

# ═══════════════════════════════ SLIDE 7 — Architecture ═════════════════════
s7 = chrome("System Architecture", "End-to-End Detection Architecture", 7)
layers = [
    ("User Activity", "logins, file access, transfers, endpoints, sessions", "browser \u00b7 React 19 + Vite"),
    ("Data Collection Layer", "behavioural windows aggregated per identity", "FastAPI \u00b7 Pydantic v2"),
    ("Preprocessing Engine", "impute \u2192 log1p \u2192 standard scale", "scikit-learn Pipeline"),
    ("Feature Engineering", "20 numeric + 3 categorical \u2192 42 columns", "pandas \u00b7 NumPy"),
    ("ML Detection Engine", "Logistic Regression probability per window", "joblib artifact"),
    ("Risk Scoring Engine", "0.40 ML + 0.30 behaviour + 0.15 asset + 0.15 privilege", "risk_engine.py"),
    ("Alert / Notification System", "8 deterministic rules, severity bands, notifications", "POST /api/v1/ingestion"),
    ("Security Dashboard", "queue, timelines, model insights, investigations", "PostgreSQL \u00b7 SQLAlchemy 2"),
]
bar_x, bar_w, bar_h, bar_gap = MX + 1450000, 6600000, 320000, 58000
y = BODY_Y + 120000
for i, (name, gloss, tech) in enumerate(layers):
    s7.append(shape(20 + i, bar_x, y, bar_w, bar_h,
                    fill=CARD_HI if i in (0, 7) else CARD,
                    line_color=ACCENT if i in (4, 5) else LINE, anchor="ctr", pad=120000,
                    paras=[para([run(name, color=TXT, sz=1100, b=1),
                                 run("   " + gloss, color=TXT_2, sz=950)], before=0)]))
    s7.append(textbox(40 + i, MX, y, 900000, bar_h, [
        para([run(f"{i + 1:02d}", color=ACCENT, sz=1000, b=1)], before=0)], anchor="ctr"))
    s7.append(textbox(50 + i, bar_x + bar_w + 140000, y, CW - (bar_x + bar_w + 140000 - MX), bar_h, [
        para([run(tech, color=TXT_3, sz=880)], before=0)], anchor="ctr"))
    if i < len(layers) - 1:
        s7.append(textbox(60 + i, bar_x, y + bar_h, bar_w, bar_gap, [
            para([run("\u2193", color=ACCENT, sz=800, b=1)], algn="ctr", before=0)], anchor="ctr"))
    y += bar_h + bar_gap
s7.append(textbox(70, MX, y + 200000, CW, 400000, [
    para([run("One FastAPI service owns authentication (JWT + refresh), RBAC across four roles, "
              "ingestion and detection; the model artifact is loaded once at startup, so "
              "inference is in-process.", color=TXT_3, sz=980)], before=0, line=102000),
]))
slides.append(slide_xml(s7))

# ═══════════════════════════════ SLIDE 8 — Dashboard / demo ═════════════════
s8 = chrome("Working Demonstration", "Security Dashboard", 8)
frames = ["Security Overview", "User Risk Scores", "Suspicious Activities", "Recent Alerts",
          "Behavioral Trends", "High-Risk Users", "Activity Timeline"]
gw = 6300000
fw = (gw - 160000) // 2
fh = 880000
for i, name in enumerate(frames):
    col, row = i % 2, i // 2
    fx = MX + col * (fw + 160000)
    fy = BODY_Y + row * (fh + 130000)
    s8.append(shape(20 + i, fx, fy, fw, fh, fill=CARD_2, line_color=LINE_HI, dash="dash",
                    anchor="ctr", pad=120000, paras=[
        para([run(name, color=TXT, sz=1150, b=1)], algn="ctr", before=0),
        para([run("screenshot placeholder \u2014 drop the captured view here",
                  color=TXT_3, sz=880)], algn="ctr", before=200),
    ]))
s8.append(shape(27, MX + gw + 180000, BODY_Y, CW - gw - 180000, 2100000, fill=CARD,
                line_color=ACCENT, anchor="t", pad=170000, paras=
                [label("WORKED EXAMPLE \u00b7 ILLUSTRATIVE", color=ACCENT)] +
                [para([run(a + "  \u2192  ", color=ACCENT, sz=1000, b=1),
                       run(b, color=TXT, sz=1000)], before=280) for a, b in [
                    ("Employee", "a finance user, privileged account"),
                    ("Deviation", "off_hours_ratio 0.82, 27 sensitive files"),
                    ("Risk score", "94 / 100 \u2192 CRITICAL"),
                    ("Alert", "OFF_HOURS_ACCESS + RESOURCE_SNOOPING"),
                    ("Investigation", "queued for an analyst with the factors attached")]]))
s8.append(shape(28, MX + gw + 180000, 4080000, CW - gw - 180000, 1840000, fill=CARD_2,
                line_color=LINE, anchor="t", pad=170000, paras=[
    label("HOW TO CAPTURE", color=TXT_3),
    bullet("Run the UI (npm run dev) and the API (docker compose up --build).", sz=1000),
    bullet("Sign in, then walk Command Center \u2192 Anomaly Queue \u2192 User Behaviour \u2192 "
           "Activity Timeline \u2192 Model Insights.", sz=1000),
    bullet("Open an alert to capture the drawer, and an employee for the peer comparison.",
           sz=1000),
    bullet("Frames above are sized for wide strips \u2014 replace each card with its capture.",
           sz=1000),
]))
slides.append(slide_xml(s8))

# ═══════════════════════════════ SLIDE 9 — Results & impact ═════════════════
s9 = chrome("Outcomes", "Results, Advantages & Security Impact", 9)
cw9 = (CW - 2 * 160000) // 3
mrows = [("Precision", "1.0000"), ("Recall", "1.0000"), ("F1 score", "1.0000"),
         ("ROC-AUC", "1.0000"), ("PR-AUC", "1.0000"), ("False-positive rate", "0.0000")]
p9 = [label("MODEL PERFORMANCE", color=ACCENT),
      para([run("Logistic Regression \u00b7 sentinel-ueba-v1 \u00b7 2,000-window synthetic holdout",
                color=TXT_3, sz=920)], before=280)]
for k, v in mrows:
    p9.append(para([run(k, color=TXT_2, sz=1000), run("   " + v, color=TXT, sz=1000, b=1)],
                   before=210))
s9.append(shape(20, MX, BODY_Y, cw9, 2760000, fill=CARD, line_color=ACCENT, anchor="t",
                pad=160000, paras=p9))
adv = ["Early detection \u2014 deviation is caught during the window, not after the breach",
       "Behavior-based, so it works without signature or IOC updates",
       "Prioritization \u2014 scores and bands replace an undifferentiated queue",
       "Explanations attached \u2014 every alert names its contributing factors",
       "Less manual analysis \u2014 rules and model agree or disagree explicitly",
       "Continuous \u2014 the same pipeline scores every identity, every window"]
s9.append(shape(21, MX + cw9 + 160000, BODY_Y, cw9, 2760000, fill=CARD, line_color=LINE,
                anchor="t", pad=160000, paras=[label("SYSTEM ADVANTAGES", color=ACCENT)] +
                [bullet(a, sz=1000, before=260) for a in adv]))
chain = [("Activity", "what the user actually did"), ("Detection", "model + rules on behaviour"),
         ("Risk assessment", "weighted 0\u2013100 score"), ("Alert", "severity + named factors"),
         ("Investigation", "analyst case with evidence"), ("Response", "containment and remediation")]
chx = MX + 2 * (cw9 + 160000)
s9.append(shape(29, chx, BODY_Y, cw9, 2760000, fill=CARD, line_color=LINE, pad=0))
s9 += vchain(30, chain, chx + 170000, BODY_Y + 170000, cw9 - 340000,
             row_h=330000, gap=76000, sz=980, fill=CARD_HI)
s9.append(shape(40, MX, 4740000, CW, 960000, fill=CARD_2, line_color=ACCENT_2, anchor="ctr",
                pad=190000, paras=[
    para([run("Where detection quality goes next: ", color=TXT, sz=1080, b=1),
          run("the current scores come from separable synthetic data, so the honest next "
              "validation step is a labelled real corpus or injected red-team activity \u2014 then "
              "the same pipeline can be judged on precision at a fixed analyst workload.",
              color=TXT_2, sz=1080)], algn="ctr", before=0, line=104000),
]))
slides.append(slide_xml(s9))

# ═══════════════════════════════ SLIDE 10 — Conclusion ══════════════════════
s10 = chrome("Conclusion", "Conclusion & Future Scope", 10)
s10.append(shape(20, MX, BODY_Y, CW, 800000, fill=CARD, line_color=ACCENT, anchor="ctr",
                 pad=200000, paras=[
    para([run("The system analyzes user behavior, identifies abnormal activity, assigns risk "
              "levels, and helps security teams ", color=TXT_2, sz=1250),
          run("prioritize potential insider threats", color=TXT, sz=1250, b=1),
          run(".", color=TXT_2, sz=1250)], algn="ctr", before=0, line=106000),
]))
s10 += flow(21, ["Detect", "Analyze", "Score", "Alert"], MX, 2720000, CW, 700000,
            gap=260000, sz=1200, node_fill=CARD_HI, node_line=ACCENT)
s10.append(textbox(26, MX, 3560000, CW, 240000, [label("FUTURE SCOPE")]))
fut = ["Real-time activity streaming", "SIEM integration", "Explainable AI",
       "User behaviour profiling", "Automated incident response",
       "Graph-based behavioural analysis", "Continuous model retraining",
       "Security-team notifications", "Zero-trust integration"]
fu = (CW - 2 * 150000) // 3
for i, f in enumerate(fut):
    col, row = i % 3, i // 3
    s10.append(shape(30 + i, MX + col * (fu + 150000), 3820000 + row * 420000, fu, 370000,
                     fill=CARD_HI, line_color=LINE, anchor="ctr", pad=110000, paras=[
        para([run(f, color=TXT_2, sz=1000, b=1)], algn="ctr", before=0)]))
s10.append(textbox(40, MX, 5110000, CW, 400000, [
    para([run("From monitoring activity to understanding behavior.", color=ACCENT, sz=1900, b=1,
              italic=1)], algn="ctr", before=0)]))
s10.append(shape(41, MX, 5550000, CW, 420000, fill=CARD_2, line_color=LINE, anchor="ctr",
                 pad=150000, paras=[
    para([run("Thank you      ", color=TXT, sz=1150, b=1),
          run("Team: [ Team Name ]  \u00b7  [ Member 1 \u00b7 Member 2 \u00b7 Member 3 ]      ",
              color=TXT_2, sz=1000),
          run("[ Department ]  \u00b7  [ Institution ]  \u00b7  [ team@institution.edu ]",
              color=TXT_3, sz=1000)], algn="ctr", before=0)]))
slides.append(slide_xml(s10))

assert len(slides) == NSLIDES, f"expected {NSLIDES} slides, got {len(slides)}"


# ── Package parts ───────────────────────────────────────────────────────────
content_types = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Types xmlns="{PKG_CT}">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
    '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
    '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
    '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
    + "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, NSLIDES + 1)
    )
    + '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
    '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
    "</Types>"
)

root_rels = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    f'<Relationship Id="rId1" Type="{PKG_REL}/officeDocument" Target="ppt/presentation.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
    f'<Relationship Id="rId3" Type="{PKG_REL}/extended-properties" Target="docProps/app.xml"/>'
    "</Relationships>"
)

presentation = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<p:presentation {NS} saveSubsetFonts="1">'
    '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
    "<p:sldIdLst>"
    + "".join(f'<p:sldId id="{256 + i}" r:id="rId{i + 2}"/>' for i in range(NSLIDES))
    + "</p:sldIdLst>"
    f'<p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}"/>'
    '<p:notesSz cx="6858000" cy="9144000"/>'
    "</p:presentation>"
)

presentation_rels = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    f'<Relationship Id="rId1" Type="{PKG_REL}/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    + "".join(
        f'<Relationship Id="rId{i + 2}" Type="{PKG_REL}/slide" Target="slides/slide{i + 1}.xml"/>'
        for i in range(NSLIDES)
    )
    + "</Relationships>"
)

empty_tree = (
    '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
    '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
    '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
)

slide_master = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f"<p:sldMaster {NS}><p:cSld>"
    f'<p:bg><p:bgPr><a:solidFill><a:srgbClr val="{BG}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'
    f"<p:spTree>{empty_tree}</p:spTree></p:cSld>"
    '<p:clrMap bg1="dk1" tx1="lt1" bg2="dk2" tx2="lt2" accent1="accent1" accent2="accent2" '
    'accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" '
    'hlink="hlink" folHlink="folHlink"/>'
    '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
    "<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>"
)

slide_master_rels = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    f'<Relationship Id="rId1" Type="{PKG_REL}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
    f'<Relationship Id="rId2" Type="{PKG_REL}/theme" Target="../theme/theme1.xml"/>'
    "</Relationships>"
)

slide_layout = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<p:sldLayout {NS} type="blank" preserve="1">'
    f'<p:cSld name="Blank"><p:spTree>{empty_tree}</p:spTree></p:cSld>'
    "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"
)

slide_layout_rels = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    f'<Relationship Id="rId1" Type="{PKG_REL}/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
    "</Relationships>"
)


def slide_rels():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{PKG_REL}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        "</Relationships>"
    )


solid = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
theme = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Sentinel">'
    "<a:themeElements>"
    '<a:clrScheme name="Sentinel">'
    f'<a:dk1><a:srgbClr val="{TXT}"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
    f'<a:dk2><a:srgbClr val="{TXT_2}"/></a:dk2><a:lt2><a:srgbClr val="{BG}"/></a:lt2>'
    f'<a:accent1><a:srgbClr val="{ACCENT}"/></a:accent1>'
    f'<a:accent2><a:srgbClr val="{ACCENT_2}"/></a:accent2>'
    f'<a:accent3><a:srgbClr val="{WARN}"/></a:accent3>'
    f'<a:accent4><a:srgbClr val="{CRIT}"/></a:accent4>'
    f'<a:accent5><a:srgbClr val="{OK}"/></a:accent5>'
    f'<a:accent6><a:srgbClr val="{TXT_3}"/></a:accent6>'
    f'<a:hlink><a:srgbClr val="{ACCENT}"/></a:hlink>'
    f'<a:folHlink><a:srgbClr val="{TXT_2}"/></a:folHlink>'
    "</a:clrScheme>"
    '<a:fontScheme name="Sentinel">'
    '<a:majorFont><a:latin typeface="Inter"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
    '<a:minorFont><a:latin typeface="Inter"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>'
    "</a:fontScheme>"
    '<a:fmtScheme name="Sentinel">'
    f"<a:fillStyleLst>{solid}{solid}{solid}</a:fillStyleLst>"
    "<a:lnStyleLst>"
    f'<a:ln w="9525" cap="flat" cmpd="sng" algn="ctr">{solid}<a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>'
    f'<a:ln w="25400" cap="flat" cmpd="sng" algn="ctr">{solid}<a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>'
    f'<a:ln w="38100" cap="flat" cmpd="sng" algn="ctr">{solid}<a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>'
    "</a:lnStyleLst>"
    "<a:effectStyleLst>"
    "<a:effectStyle><a:effectLst/></a:effectStyle>"
    "<a:effectStyle><a:effectLst/></a:effectStyle>"
    "<a:effectStyle><a:effectLst/></a:effectStyle>"
    "</a:effectStyleLst>"
    f"<a:bgFillStyleLst>{solid}{solid}{solid}</a:bgFillStyleLst>"
    "</a:fmtScheme>"
    "</a:themeElements>"
    "<a:objectDefaults/><a:extraClrSchemeLst/>"
    "</a:theme>"
)

core = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:dcterms="http://purl.org/dc/terms/" '
    'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    "<dc:title>Insider Threat Detection System</dc:title>"
    "<dc:subject>AI-Powered Behavioral Analytics for Enterprise Security</dc:subject>"
    "<dc:creator>Insider Threat Detection System</dc:creator>"
    "<cp:lastModifiedBy>Insider Threat Detection System</cp:lastModifiedBy>"
    "</cp:coreProperties>"
)

app = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
    'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
    "<Application>Microsoft Office PowerPoint</Application>"
    f"<Slides>{NSLIDES}</Slides>"
    "<Company>Insider Threat Detection System</Company>"
    "</Properties>"
)

parts = {
    "[Content_Types].xml": content_types,
    "_rels/.rels": root_rels,
    "docProps/core.xml": core,
    "docProps/app.xml": app,
    "ppt/presentation.xml": presentation,
    "ppt/_rels/presentation.xml.rels": presentation_rels,
    "ppt/slideMasters/slideMaster1.xml": slide_master,
    "ppt/slideMasters/_rels/slideMaster1.xml.rels": slide_master_rels,
    "ppt/slideLayouts/slideLayout1.xml": slide_layout,
    "ppt/slideLayouts/_rels/slideLayout1.xml.rels": slide_layout_rels,
    "ppt/theme/theme1.xml": theme,
}
for i, sld in enumerate(slides, start=1):
    parts[f"ppt/slides/slide{i}.xml"] = sld
    parts[f"ppt/slides/_rels/slide{i}.xml.rels"] = slide_rels()

if os.path.exists(OUT):
    os.remove(OUT)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for name, data in parts.items():
        z.writestr(name, data)

print(f"Wrote {OUT}  ({os.path.getsize(OUT):,} bytes, {len(slides)} slides)")
