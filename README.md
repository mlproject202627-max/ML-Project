# Sentinel — Insider Threat Detection UI

A dark-themed **UEBA (User & Entity Behaviour Analytics)** command center for insider
threat detection, focused on **user behaviour and access anomalies**: off-hours access,
lateral movement, peer-group deviation, privilege escalation, impossible travel,
dormant-account revival, resource sweeping and session anomalies.

> ⚠️ **UI only.** There is no ML runtime in this project. Every identity, alert,
> metric and event is deterministic synthetic sample data defined in
> `src/data/mock.ts` — no models are trained, loaded or called.

## Stack

| Concern | Choice |
| --- | --- |
| Framework | React 19 + TypeScript |
| Build | Vite 8 |
| Styling | Tailwind CSS v4 (`@theme` design tokens, custom `@utility` layers) |
| Charts | Recharts 3 |
| Icons | lucide-react |

## Running it

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # typecheck + production bundle into dist/
npm run preview  # serve the production build
npm run lint     # oxlint
```

## Views

| View | What it shows |
| --- | --- |
| **Command Center** | KPI band, anomaly-vs-risk trend, detection mix donut, priority triage, highest-drift identities, 7-day access heatmap, department risk, live access stream |
| **User Behaviour** | Highest-risk identity spotlight (radar vs peer group, baseline drift, 24h intensity) plus a sortable table of every monitored identity |
| **Anomaly Queue** | Severity summary cards, status/class filters, sortable triage list with confidence meters |
| **Activity Timeline** | Weekday×hour heatmap, hour-of-day distribution, vertical detection timeline, filterable event stream, anomaly-class reference |
| **Model Insights** | Detector fleet health (precision/recall/F1/AUC, drift), global feature attribution, training cadence |
| **Detection Policy** | Sensitivity sliders, detector enable/disable, alert routing, watchlist management, data governance and audit trail |

Two right-hand drawers provide the investigation surface: an **alert drawer**
(narrative, contributing-factor attribution, context, containment actions) and an
**employee drawer** (peer-comparison radar, baseline drift table, 24h pattern,
linked detections). They cross-link to each other.

## Structure

```
src/
├─ App.tsx                    shell, view routing, drawer orchestration, ⌘K search
├─ index.css                  design tokens, base layer, custom utilities
├─ data/
│  ├─ types.ts                domain model
│  └─ mock.ts                 deterministic synthetic dataset + peerBaseline()
├─ lib/
│  ├─ nav.ts                  navigation model
│  └─ utils.ts                formatting, risk tones, relative time
└─ components/
   ├─ layout/                 PrimaryNav (top dropdown menus), PageHeader,
   │                          Logomark, PostureWidget
   ├─ ui/                     Panel, Badge, Avatar, Meter, RiskDial, Segmented,
   │                          Sparkline, StatCard, Ticker, Drawer, Controls
   ├─ charts/                 RiskTrendChart, BehaviourRadar, KindDonut,
   │                          ActivityHeatmap, HourStrip, FactorBars, DeptBars
   ├─ lists/                  AlertRow, IdentityRow, EventFeed
   ├─ detail/                 AlertDrawer, EmployeeDrawer
   └─ views/                  the six views above
```

## Navigation

A full-width top bar carries the primary navigation as two dropdown menus
(**Monitoring** and **Platform**), grouped the same way the side menu was. Menus
open on click, switch on hover once open, and close on outside-click or `Escape`.
Below `lg` they collapse into a single **Menu** button. The page header below the
nav holds the view title plus the range and export controls.

## Design notes

### Colour system — "Obsidian Luxury + Ice Blue"

A near-black obsidian base with neutral typography and a single scarce accent.

| Role | Value |
| --- | --- |
| App background | `#050607` |
| Nav surface | `#08090B` |
| Card surface | `#0D0F12` |
| Elevated surface | `#111419` |
| Overlay surface | `#14171B` |
| Border / divider / hover | `#252A30` / `#1A1D21` / `#343A41` |
| Primary / secondary / muted text | `#F5F7FA` / `#A7AFB8` / `#69717A` |
| Accent (Ice Blue) | `#7DD3FC` |
| Critical / Warning / Success | `#FDA4AF` / `#FDE68A` / `#A7F3D0` |

- **Ice blue is scarce (~3%)** — active nav, focus rings, selected filters and
  small status indicators only. Never large fills, cards or text blocks.
- **Severity is a four-step ramp**, alarming → calm: critical `#FDA4AF` → high
  `#FDE68A` → medium `#A7F3D0` → low muted `#69717A`. It never colours whole rows.
- **Charts are exempt.** Every plot draws from `GRAPH` in `lib/utils.ts` — a
  separate palette deliberately left colourful so data series stay distinguishable
  against the monochrome chrome. Axis labels and gridlines stay obsidian/grayscale.

### Other

- **Tokens over ad-hoc colours.** The palette lives in `@theme` in `index.css`,
  so surfaces (`bg-surface`, `border-line`), text (`text-fg`, `text-muted`,
  `text-faint`) and the accent are semantic and globally consistent.
- **Flat surfaces, no glass.** No backdrop blur and no neon glows — depth comes
  from hairline borders and restrained shadows.
- **Reachability.** Charts are code-split, so the initial bundle is ~289 kB and the
  Recharts chunk (~308 kB) loads only when a view needs it.
- **Accessibility.** Focus-visible rings, `aria-expanded`/`aria-haspopup` on nav
  menus, `role="switch"`/`aria-checked` on toggles, `aria-selected` on segmented
  controls, escape-to-close drawers and menus, `title` tooltips on heatmap cells,
  and a `prefers-reduced-motion` block that disables animation.
