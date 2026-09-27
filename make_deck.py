#!/usr/bin/env python3
"""
One-off generator for Sentinel-Project-Overview.pptx  (8 slides)

Builds a valid OOXML deck using only the Python standard library,
so no third-party packages (python-pptx) or virtualenv are required.

Run:  python3 make_deck.py
"""
import os
import zipfile
from xml.sax.saxutils import escape as esc

OUT = "Sentinel-Project-Overview.pptx"
NSLIDES = 8

# ── Brand palette (light / creamy) ──────────────────────────────────────────
BG        = "F6EDDD"   # warm cream base
BG_TOP    = "FFFDF8"   # near-white top stop
CARD      = "FFFFFF"   # elevated surface
CARD_2    = "FDF8EC"   # cream tint
CARD_HI   = "FBF4E4"   # deep cream chip
LINE      = "E8DDC8"
LINE_HI   = "DCCDB1"
ACCENT    = "0E7490"   # deep teal
ACCENT_2  = "C2410C"   # burnt rust
VIOLET    = "7E22CE"
TXT       = "241C14"   # espresso ink
TXT_2     = "6A5B49"
TXT_3     = "7C6A4E"
GHOST     = "EBDFC8"
CRIT      = "BE123C"
WARN      = "8A5406"
OK        = "166534"

# ── Slide geometry (16:9, EMU) ──────────────────────────────────────────────
SLIDE_W = 12192000
SLIDE_H = 6858000
MX      = 838200            # left/right margin
CW      = SLIDE_W - 2 * MX  # content width

NS = (
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
)
PKG_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


# ── XML helpers ─────────────────────────────────────────────────────────────
def run(text, color=TXT_2, sz=1300, b=0, italic=0, font="Inter"):
    return (
        f'<a:r><a:rPr lang="en-US" sz="{sz}" b="{b}" i="{italic}" dirty="0">'
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


def bullet(text, color=TXT_2, sz=1200, marker="\u2013", before=480, mcolor=ACCENT, b=0):
    """A bulleted line: accent marker + body text."""
    return para(
        [run(marker + "   ", color=mcolor, sz=sz, b=1), run(text, color=color, sz=sz, b=b)],
        before=before,
    )


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


def shadow_xml(color="8A7350", alpha=18000, blur=120000, dist=26000):
    """Soft warm drop shadow so cards read as elevated on a light canvas."""
    return (
        f'<a:effectLst><a:outerShdw blurRad="{blur}" dist="{dist}" dir="5400000" '
        f'rotWithShape="0"><a:srgbClr val="{color}"><a:alpha val="{alpha}"/>'
        f"</a:srgbClr></a:outerShdw></a:effectLst>"
    )


def shape(sid, x, y, cx, cy, fill=CARD, paras=None, prst="roundRect",
          line_color=None, anchor="t", pad=180000, alpha=None, fill2=None,
          grad_ang=5400000, line_w=9525, shadow=None):
    ln = (
        f'<a:ln w="{line_w}"><a:solidFill><a:srgbClr val="{line_color}"/></a:solidFill></a:ln>'
        if line_color
        else "<a:ln><a:noFill/></a:ln>"
    )
    # Rounded cards and chips lift off the page; bars, rules and glows stay flat.
    fx = shadow_xml() if (shadow is True or (shadow is None and prst == "roundRect")) else ""
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


def glow(sid, x, y, size, color=ACCENT, alpha=7000):
    """Soft decorative halo, drawn behind everything else."""
    return shape(sid, x, y, size, size, fill=color, alpha=alpha, prst="ellipse")


# ── Slide chrome (accent bar + eyebrow + title + rule + ghost numeral + footer)
def chrome(eyebrow, title, page):
    return [
        glow(11, SLIDE_W - 3400000, -1500000, 4200000, ACCENT, 9500),
        glow(12, -1500000, SLIDE_H - 1900000, 3200000, ACCENT_2, 6500),
        shape(3, 0, 0, SLIDE_W, 26000, fill=ACCENT, fill2=ACCENT_2, prst="rect", grad_ang=0),
        textbox(4, SLIDE_W - MX - 1700000, 430000, 1700000, 950000, [
            para([run(f"{page:02d}", color=GHOST, sz=5400, b=1)], algn="r", before=0)
        ]),
        textbox(5, MX, 640000, CW, 260000, [
            para([run(eyebrow.upper(), color=ACCENT, sz=1050, b=1)], before=0)
        ]),
        textbox(6, MX, 920000, CW, 620000, [
            para([run(title, color=TXT, sz=3000, b=1)], before=0)
        ]),
        shape(7, MX, 1620000, 620000, 30000, fill=ACCENT, fill2=ACCENT_2, prst="rect", grad_ang=0),
        textbox(8, MX, SLIDE_H - 640000, CW, 300000, [
            para([run("Sentinel  \u00b7  Insider Threat Detection (UEBA)  \u00b7  all data synthetic",
                     color=TXT_3, sz=950)], before=0)
        ]),
        textbox(9, SLIDE_W - MX - 900000, SLIDE_H - 640000, 900000, 300000, [
            para([run(f"{page} / {NSLIDES}", color=TXT_3, sz=950)], algn="r", before=0)
        ]),
    ]


slides = []

# ─────────────────────────────────────────────────────────────── Slide 1 ──
# Title
chips = [("8", "anomaly classes"), ("6", "analyst views"),
         ("23", "model features"), ("\u224840", "REST endpoints")]
chip_w = (CW - 3 * 200000) // 4
s1 = [
    glow(11, SLIDE_W - 3600000, -1700000, 4800000, ACCENT, 12000),
    glow(12, -1800000, SLIDE_H - 2400000, 4200000, ACCENT_2, 8000),
    shape(3, 0, 0, SLIDE_W, 30000, fill=ACCENT, fill2=ACCENT_2, prst="rect", grad_ang=0),
    textbox(4, MX, 2050000, CW, 300000, [
        para([run("INSIDER THREAT DETECTION  \u00b7  UEBA", color=ACCENT, sz=1200, b=1)], before=0)
    ]),
    textbox(5, MX, 2400000, CW, 1200000, [
        para([run("Sentinel", color=TXT, sz=7200, b=1)], before=0)
    ]),
    shape(6, MX, 3660000, 900000, 34000, fill=ACCENT, fill2=ACCENT_2, prst="rect", grad_ang=0),
    textbox(7, MX, 3860000, 8700000, 700000, [
        para([run("A user-behaviour analytics command center that detects insider threats \u2014 "
                  "people deviating from their own baseline or from their peer group, not malware.",
                  color=TXT_2, sz=1500)], line=112000, before=0)
    ]),
    textbox(8, MX, 4620000, CW, 400000, [
        para([run("React 19  \u00b7  Vite  \u00b7  FastAPI  \u00b7  PostgreSQL  \u00b7  scikit-learn  \u00b7  "
                  "Tailwind v4  \u00b7  Recharts", color=TXT_3, sz=1150)], before=0)
    ]),
]
for i, (big, label) in enumerate(chips):
    s1.append(shape(20 + i, MX + i * (chip_w + 200000), 5280000, chip_w, 620000,
                    fill=CARD_HI, line_color=LINE_HI, anchor="ctr", pad=120000, paras=[
        para([run(big, color=ACCENT, sz=1900, b=1),
              run("   " + label, color=TXT_2, sz=1100)], before=0),
    ]))
slides.append(slide_xml(s1))

# ─────────────────────────────────────────────────────────────── Slide 2 ──
# What Sentinel Is
s2 = chrome("The Product", "What Sentinel Is", 2)
s2 += [
    textbox(20, MX, 1860000, CW, 460000, [
        para([run("Behaviour-based security analytics: Sentinel watches what accounts ",
                  color=TXT_2, sz=1400),
              run("do", color=TXT, sz=1400, b=1),
              run(" \u2014 not what malware does. Every alert resolves to a person whose activity "
                  "has shifted away from their own baseline or away from their peer group.",
                  color=TXT_2, sz=1400)], line=112000, before=0)
    ]),
    shape(21, MX, 2620000, 3380000, 1460000, fill=CARD, line_color=ACCENT, anchor="t", paras=[
        para([run("6 ANALYST VIEWS", color=ACCENT, sz=1050, b=1)], before=0),
        para([run("Command Center, Anomaly Queue, User Behaviour, Activity Timeline, "
                  "Model Insights, Detection Policies \u2014 one sidebar, four nav groups.",
                  color=TXT_2, sz=1130)], before=500),
    ]),
    shape(22, MX + 3540000, 2620000, 3380000, 1460000, fill=CARD, line_color=LINE, anchor="t", paras=[
        para([run("INVESTIGATION SURFACE", color=TXT_2, sz=1050, b=1)], before=0),
        para([run("Two cross-linked drawers: alert detail (narrative, contributing factors, "
                  "containment) and employee peer-comparison.", color=TXT_2, sz=1130)], before=500),
    ]),
    shape(23, MX + 7080000, 2620000, 3380000, 1460000, fill=CARD, line_color=LINE, anchor="t", paras=[
        para([run("HONEST SCOPE", color=TXT_2, sz=1050, b=1)], before=0),
        para([run("All identities, events and detections are deterministic synthetic data. "
                  "No real security telemetry, no production guarantees.",
                  color=TXT_2, sz=1130)], before=500),
    ]),
    textbox(24, MX, 4360000, CW, 320000, [
        para([run("THE EIGHT ANOMALY CLASSES", color=TXT_3, sz=1000, b=1)], before=0)
    ]),
    shape(25, MX, 4720000, CW, 1240000, fill=CARD_2, line_color=LINE, anchor="ctr", paras=[
        para([run("Off-hours access", color=CRIT, sz=1200, b=1),
              run("      Lateral movement", color=WARN, sz=1200, b=1),
              run("      Peer deviation", color=OK, sz=1200, b=1),
              run("      Privilege escalation", color=CRIT, sz=1200, b=1)], before=0),
        para([run("Impossible travel", color=WARN, sz=1200, b=1),
              run("      Dormant-account revival", color=OK, sz=1200, b=1),
              run("      Resource sweeping", color=CRIT, sz=1200, b=1),
              run("      Session anomaly", color=WARN, sz=1200, b=1)], before=650),
    ]),
]
slides.append(slide_xml(s2))

# ─────────────────────────────────────────────────────────────── Slide 3 ──
# Architecture
s3 = chrome("How It Fits Together", "Architecture: Two Halves, One Seam", 3)
box_w = 3380000
s3 += [
    shape(20, MX, 1980000, box_w, 1900000, fill=CARD, line_color=ACCENT, anchor="t", paras=[
        para([run("FRONTEND", color=ACCENT, sz=1050, b=1)], before=0),
        para([run("src/  \u00b7  React 19 + TypeScript", color=TXT, sz=1350, b=1)], before=350),
        para([run("Vite, Tailwind v4 design tokens, Recharts, lucide-react. Six code-split views "
                  "behind a sidebar + top-bar shell, with two detail drawers.",
                  color=TXT_2, sz=1120)], before=450),
    ]),
    shape(21, MX + 3540000, 1980000, box_w, 1900000, fill=CARD, line_color=LINE, anchor="t", paras=[
        para([run("BACKEND", color=TXT_2, sz=1050, b=1)], before=0),
        para([run("backend/app/  \u00b7  FastAPI + SQLAlchemy 2", color=TXT, sz=1350, b=1)], before=350),
        para([run("PostgreSQL, Alembic migrations, Pydantic v2 schemas, JWT auth and RBAC across "
                  "ten routers.", color=TXT_2, sz=1120)], before=450),
    ]),
    shape(22, MX + 7080000, 1980000, box_w, 1900000, fill=CARD, line_color=LINE, anchor="t", paras=[
        para([run("ML PIPELINE", color=TXT_2, sz=1050, b=1)], before=0),
        para([run("backend/ml/  \u00b7  scikit-learn", color=TXT, sz=1350, b=1)], before=350),
        para([run("Synthetic data generator, preprocessing, training, a joblib artifact, a "
                  "weighted risk engine and a deterministic rule engine.",
                  color=TXT_2, sz=1120)], before=450),
    ]),
    shape(23, MX, 4080000, CW, 1800000, fill=CARD_2, line_color=WARN, anchor="t", paras=[
        para([run("THE SEAM  \u2014  and the single most important thing to understand",
                  color=WARN, sz=1200, b=1)], before=0),
        bullet("Auth is wired end to end: the login page calls POST /api/v1/auth/login, stores "
               "JWTs and restores the session via /auth/me.", sz=1170),
        bullet("Dashboard data is still mocked: every view imports from src/data/mock.ts, while a "
               "full typed API client sits in src/lib/api.ts \u2014 unused by the views.", sz=1170),
    ]),
]
slides.append(slide_xml(s3))

# ─────────────────────────────────────────────────────────────── Slide 4 ──
# The analyst experience
s4 = chrome("The Front End", "The Analyst Experience", 4)
LW = 5100000
RW = CW - LW - 200000
RX = MX + LW + 200000
s4 += [
    textbox(20, MX, 1840000, CW, 420000, [
        para([run("A keyboard-first triage console: one shell, six destinations, two drawers, and "
                  "no page reloads anywhere.", color=TXT_2, sz=1330)], line=112000, before=0)
    ]),
    shape(21, MX, 2320000, LW, 2480000, fill=CARD, line_color=ACCENT, anchor="t", paras=[
        para([run("SIX VIEWS, ONE SHELL", color=ACCENT, sz=1050, b=1)], before=0),
        bullet("States, not routes: App.tsx owns the active view, and Landing \u2192 Login \u2192 "
               "Shell is a plain state machine behind an auth gate.", sz=1160),
        bullet("Four nav groups \u2014 Overview, Detection, Behaviour, Intelligence \u2014 drive the "
               "sidebar, breadcrumbs and the \u2318K search focus.", sz=1160),
        bullet("Views are React.lazy code-split behind a Suspense skeleton, so the shell paints "
               "instantly and a slow view never blocks navigation.", sz=1160),
        bullet("A collapsible sidebar plus shared search state keep triage keyboard-first.",
               sz=1160),
    ]),
    shape(22, RX, 2320000, RW, 1180000, fill=CARD, line_color=LINE, anchor="t", paras=[
        para([run("THE INVESTIGATION SURFACE", color=TXT_2, sz=1050, b=1)], before=0),
        para([run("The alert drawer carries the narrative, contributing factors, asset and "
                  "containment actions; the employee drawer carries peer comparison and baseline "
                  "drift. They cross-link, so a hunch can be followed in either direction.",
                  color=TXT_2, sz=1110)], before=430),
    ]),
    shape(23, RX, 3640000, RW, 1160000, fill=CARD, line_color=LINE, anchor="t", paras=[
        para([run("DESIGN LANGUAGE", color=TXT_2, sz=1050, b=1)], before=0),
        para([run("Tailwind v4 CSS variables carry a light/dark token set; Recharts draws the "
                  "radar, donut, trend and activity-heat visuals; lucide supplies the icons, and a "
                  "monospace class renders every score.", color=TXT_2, sz=1110)], before=430),
    ]),
    textbox(24, MX, 4940000, CW, 280000, [
        para([run("WHERE THE SIX VIEWS LIVE", color=TXT_3, sz=1000, b=1)], before=0)
    ]),
]
views = ["Command Center", "Anomaly Queue", "User Behaviour", "Activity Timeline",
         "Model Insights", "Detection Policies"]
vw = (CW - 5 * 180000) // 6
for i, v in enumerate(views):
    s4.append(shape(30 + i, MX + i * (vw + 180000), 5240000, vw, 560000,
                    fill=CARD_HI, line_color=LINE_HI, anchor="ctr", pad=100000, paras=[
        para([run(v, color=TXT_2, sz=950, b=1)], algn="ctr", before=0)
    ]))
slides.append(slide_xml(s4))

# ─────────────────────────────────────────────────────────────── Slide 5 ──
# Domain model & data flow
s5 = chrome("The Data Layer", "Domain Model & Detection Flow", 5)
entities = [
    ("User", "identity, role, department, peer group"),
    ("ActivityEvent", "raw telemetry with a verdict"),
    ("Anomaly", "a detection: kind, severity, score"),
    ("RiskEvent", "per-signal weight breakdown"),
    ("Investigation", "the case workflow and owner"),
    ("DetectionPolicy", "thresholds and rule switches"),
    ("Notification", "what an analyst gets told"),
]
s5 += [
    textbox(20, MX, 1840000, CW, 400000, [
        para([run("Seven persisted entities, one rule: everything resolves to a person deviating "
                  "from their baseline.", color=TXT_2, sz=1330)], line=112000, before=0)
    ]),
]
paras_e = [para([run("SEVEN PERSISTED ENTITIES", color=ACCENT, sz=1050, b=1)], before=0)]
for name, desc in entities:
    paras_e.append(para([run(name + "   ", color=TXT, sz=1180, b=1),
                         run(desc, color=TXT_2, sz=1130)], before=300))
s5.append(shape(21, MX, 2300000, LW, 2360000, fill=CARD, line_color=ACCENT,
                anchor="t", pad=160000, paras=paras_e))
s5.append(shape(22, RX, 2300000, RW, 2360000, fill=CARD_2, line_color=WARN, anchor="t", paras=[
    para([run("THE ENUM SEAM", color=WARN, sz=1050, b=1)], before=0),
    para([run("The UI speaks lowercase snake_case \u2014 ", color=TXT_2, sz=1120),
          run("'off_hours_access'", color=ACCENT, sz=1120, b=1),
          run(", severity ", color=TXT_2, sz=1120),
          run("'critical'", color=ACCENT, sz=1120, b=1),
          run(". The API speaks UPPER_SNAKE. Any adapter between them has to normalise in both "
              "directions.", color=TXT_2, sz=1120)], before=430),
    para([run("The model also has two lineages today: two seed scripts and two detector "
              "abstractions coexist \u2014 one serving the API, one serving the ML pipeline.",
              color=TXT_2, sz=1120)], before=430),
]))
s5.append(textbox(24, MX, 4760000, CW, 280000, [
    para([run("THE DETECTION PATH", color=TXT_3, sz=1000, b=1)], before=0)
]))
flow = ["Ingest", "Activity Event", "Detectors", "Anomaly", "Risk Event", "Investigation"]
fw = (CW - 5 * 180000) // 6
for i, node in enumerate(flow):
    x = MX + i * (fw + 180000)
    s5.append(shape(30 + i, x, 5020000, fw, 700000, fill=CARD, line_color=LINE,
                    anchor="ctr", pad=100000, paras=[
        para([run(node, color=TXT, sz=1030, b=1)], algn="ctr", before=0),
    ]))
    if i < len(flow) - 1:
        s5.append(textbox(60 + i, x + fw, 5020000, 180000, 700000, [
            para([run("\u2192", color=ACCENT, sz=1500, b=1)], algn="ctr", before=0)
        ], anchor="ctr"))
slides.append(slide_xml(s5))

# ─────────────────────────────────────────────────────────────── Slide 6 ──
# ML pipeline
s6 = chrome("Detection Intelligence", "The ML Pipeline, End to End", 6)
steps = [
    ("Generate", "10k rows", "8% threats"),
    ("Preprocess", "23 features", "log + scale"),
    ("Train", "LogReg vs RF", "best F1"),
    ("Infer", "joblib", "probability"),
    ("Score", "weighted", "0\u2013100"),
    ("Rules", "8 deterministic", "signals"),
]
bw, gap = 1620000, 120000
for i, (head, a, b) in enumerate(steps):
    x = MX + i * (bw + gap)
    s6.append(shape(20 + i, x, 1960000, bw, 920000, fill=CARD, line_color=LINE,
                    anchor="ctr", pad=90000, paras=[
        para([run(head, color=ACCENT, sz=1200, b=1)], algn="ctr", before=0),
        para([run(a, color=TXT_2, sz=900)], algn="ctr", before=250),
        para([run(b, color=TXT_3, sz=900)], algn="ctr", before=60),
    ]))
s6 += [
    shape(30, MX, 3080000, 5900000, 1560000, fill=CARD, line_color=ACCENT, anchor="t", paras=[
        para([run("RISK SCORE  \u2014  ml/risk_engine.py", color=TXT, sz=1250, b=1)], before=0),
        para([run("0.40 \u00d7 ML probability   +   0.30 \u00d7 behavioural signals   +   "
                  "0.15 \u00d7 asset criticality   +   0.15 \u00d7 privilege context",
                  color=ACCENT, sz=1120)], before=500),
        para([run("Clamped to 0\u2013100, then bucketed into a severity band and paired with a "
                  "plain-English explanation of the dominant signals.",
                  color=TXT_3, sz=1050)], before=450),
    ]),
    shape(31, MX + 6060000, 3080000, 4600000, 1560000, fill=CARD, line_color=LINE, anchor="t", paras=[
        para([run("SEVERITY BANDS", color=TXT, sz=1250, b=1)], before=0),
        para([run("LOW  ", color=TXT_3, sz=1200, b=1), run("0\u201339      ", color=TXT_2, sz=1200),
              run("MEDIUM  ", color=TXT_3, sz=1200, b=1), run("40\u201369", color=TXT_2, sz=1200)],
             before=550),
        para([run("HIGH  ", color=WARN, sz=1200, b=1), run("70\u201389     ", color=TXT_2, sz=1200),
              run("CRITICAL  ", color=CRIT, sz=1200, b=1), run("90\u2013100", color=TXT_2, sz=1200)],
             before=420),
        para([run("Bands map back onto the UI's severity labels.", color=TXT_3, sz=1020)],
             before=430),
    ]),
    textbox(32, MX, 4820000, CW, 480000, [
        para([run("Explainability is first-class: ", color=TXT, sz=1200, b=1),
              run("the artifact stores normalised feature importances, every prediction returns "
                  "its top risk factors, and persisted risk_event rows record each signal's "
                  "weight and contribution.", color=TXT_2, sz=1200)], line=112000, before=0)
    ]),
]
slides.append(slide_xml(s6))

# ─────────────────────────────────────────────────────────────── Slide 7 ──
# Security & API
s7 = chrome("Platform", "Security & API Surface", 7)
s7 += [
    shape(20, MX, 1960000, 5900000, 2120000, fill=CARD, line_color=ACCENT, anchor="t", paras=[
        para([run("ROLE-BASED ACCESS CONTROL", color=ACCENT, sz=1050, b=1)], before=0),
        para([run("ADMIN", color=CRIT, sz=1200, b=1),
              run("   full access, delete policies, ingest data", color=TXT_2, sz=1150)], before=450),
        para([run("SECURITY_MANAGER", color=WARN, sz=1200, b=1),
              run("   policies, assign investigations", color=TXT_2, sz=1150)], before=380),
        para([run("SECURITY_ANALYST", color=OK, sz=1200, b=1),
              run("   anomalies, ML predictions, cases", color=TXT_2, sz=1150)], before=380),
        para([run("VIEWER", color=TXT_3, sz=1200, b=1),
              run("   read-only dashboard", color=TXT_2, sz=1150)], before=380),
    ]),
    shape(21, MX + 6060000, 1960000, 4600000, 2120000, fill=CARD, line_color=LINE, anchor="t", paras=[
        para([run("AUTH & HARDENING", color=ACCENT, sz=1050, b=1)], before=0),
        bullet("JWT access (30 min) + refresh (7 day) tokens, bcrypt hashing", sz=1120),
        bullet("CORS allow-list, security headers, request IDs and timing", sz=1120),
        bullet("Global 500 handler, IDOR-safe lookups, audit trails", sz=1120),
        bullet("~40 endpoints under /api/v1, documented at /docs", sz=1120),
    ]),
    shape(22, MX, 4240000, CW, 1660000, fill=CARD_2, line_color=LINE, anchor="t", paras=[
        para([run("API GROUPS", color=TXT_3, sz=1050, b=1)], before=0),
        para([run("auth  \u00b7  dashboard  \u00b7  users  \u00b7  anomalies  \u00b7  investigations  \u00b7  "
                  "activity  \u00b7  policies  \u00b7  notifications  \u00b7  ingestion  \u00b7  ml",
                  color=TXT, sz=1280, b=1)], before=420),
        para([run("Demo accounts (development only):   ", color=TXT_3, sz=1100),
              run("admin@sentinel.demo / Admin123!", color=TXT_2, sz=1100),
              run("     sarah.chen@sentinel.demo / Analyst123!", color=TXT_2, sz=1100)], before=600),
    ]),
]
slides.append(slide_xml(s7))

# ─────────────────────────────────────────────────────────────── Slide 8 ──
# Getting started & where to look first
s8 = chrome("Takeaways", "Getting Started & Where to Look", 8)
s8 += [
    shape(20, MX, 1960000, 5900000, 2120000, fill=CARD, line_color=ACCENT, anchor="t", paras=[
        para([run("RUN IT", color=ACCENT, sz=1050, b=1)], before=0),
        bullet("npm install && npm run dev      \u2192  UI at :5173", sz=1150),
        bullet("docker compose up --build      \u2192  API at :8000", sz=1150),
        bullet("python ml/train.py             \u2192  build the model artifact", sz=1150),
        bullet("pytest tests/ -v               \u2192  backend test suite", sz=1150),
    ]),
    shape(21, MX + 6060000, 1960000, 4600000, 2120000, fill=CARD, line_color=LINE, anchor="t", paras=[
        para([run("WHERE TO LOOK FIRST", color=ACCENT, sz=1050, b=1)], before=0),
        bullet("src/App.tsx \u2014 the shell, the view switch and both drawers", sz=1120),
        bullet("src/data/mock.ts + any view \u2014 how a screen is actually built", sz=1120),
        bullet("src/lib/api.ts \u2014 the typed client that already talks to the API", sz=1120),
        bullet("backend/app/main.py and ml/inference.py \u2014 the detection path", sz=1120),
    ]),
    shape(22, MX, 4240000, CW, 1660000, fill=CARD_2, line_color=WARN, anchor="t", paras=[
        para([run("KNOWN ROUGH EDGES", color=WARN, sz=1050, b=1)], before=0),
        para([run("Enum casing between UI and API, two seed scripts and two detector "
                  "abstractions, and two small config typos "
                  "(ACCESS_TOKEN_EXPIME_MINUTES, autoflush) \u2014 all low-risk, high-clarity fixes.",
                  color=TXT_2, sz=1170)], before=480),
        para([run("Bigger opportunity: point one view at the API client and retire its mock "
                  "import \u2014 the seam closes one screen at a time.",
                  color=TXT_3, sz=1120)], before=430),
    ]),
]
slides.append(slide_xml(s8))

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
    f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
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
    f'<a:dk1><a:srgbClr val="{BG}"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
    f'<a:dk2><a:srgbClr val="{CARD}"/></a:dk2><a:lt2><a:srgbClr val="{TXT}"/></a:lt2>'
    f'<a:accent1><a:srgbClr val="{ACCENT}"/></a:accent1>'
    f'<a:accent2><a:srgbClr val="{OK}"/></a:accent2>'
    f'<a:accent3><a:srgbClr val="{WARN}"/></a:accent3>'
    f'<a:accent4><a:srgbClr val="{CRIT}"/></a:accent4>'
    f'<a:accent5><a:srgbClr val="{TXT_2}"/></a:accent5>'
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
    "<dc:title>Sentinel \u2014 Project Overview</dc:title>"
    "<dc:subject>Insider threat detection (UEBA) platform</dc:subject>"
    "<dc:creator>Sentinel</dc:creator>"
    "<cp:lastModifiedBy>Sentinel</cp:lastModifiedBy>"
    "</cp:coreProperties>"
)

app = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
    'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
    "<Application>Microsoft Office PowerPoint</Application>"
    f"<Slides>{NSLIDES}</Slides>"
    "<Company>Sentinel</Company>"
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
