# Sentinel — Project Guide

> A single onboarding document for the **Sentinel** insider-threat detection (UEBA) platform.
> Read this top-to-bottom to go from "what is this repo?" to "how does every piece work?".

---

## Table of contents

1. [What this project is](#1-what-this-project-is)
2. [The two halves of the repo (read this first)](#2-the-two-halves-of-the-repo-read-this-first)
3. [Tech stack](#3-tech-stack)
4. [Repository layout](#4-repository-layout)
5. [Getting it running](#5-getting-it-running)
6. [Domain model & vocabulary](#6-domain-model--vocabulary)
7. [Frontend architecture](#7-frontend-architecture)
8. [Backend architecture](#8-backend-architecture)
9. [The ML / detection pipeline](#9-the-ml--detection-pipeline)
10. [API reference](#10-api-reference)
11. [Auth, RBAC & security](#11-auth-rbac--security)
12. [Environment variables](#12-environment-variables)
13. [Testing](#13-testing)
14. [Deployment](#14-deployment)
15. [Conventions, quirks & gotchas](#15-conventions-quirks--gotchas)
16. [Suggested learning path](#16-suggested-learning-path)
17. [Glossary](#17-glossary)

---

## 1. What this project is

**Sentinel** is a **UEBA (User & Entity Behaviour Analytics)** command center for **insider
threat detection**. Instead of chasing malware, it focuses on *people*: a monitored identity
deviating from its own baseline or its peer group.

It detects eight behavioural **anomaly classes**:

| Class | Meaning |
| --- | --- |
| `off_hours_access` | Activity inside the 22:00–06:00 window |
| `lateral_movement` | Jumping across hosts/systems with elevated velocity |
| `peer_deviation` | Statistical distance from the peer-group centroid |
| `privilege_escalation` | Use of elevated/admin entitlements outside change windows |
| `impossible_travel` | Geographically impossible consecutive access |
| `dormant_revival` | A long-dormant account suddenly becoming active |
| `resource_sweeping` | Rapid enumeration of many resources/shares |
| `session_anomaly` | Odd session duration / replay / fingerprint signals |

The product surface is a dark/light analyst workspace: a **Command Center**, a **User
Behaviour** explorer, an **Anomaly Queue**, an **Activity Timeline**, **Model Insights**, and
**Detection Policies**, plus two investigation drawers (alert + employee).

> ⚠️ **Everything is synthetic.** The dataset, identities, alerts and events are generated demo
> data. The ML model is trained on a **synthetic** dataset (`backend/ml/generate_dataset.py`).
> Nothing here is a production security guarantee.

---

## 2. The two halves of the repo (read this first)

This is the single most important thing to understand, because the docs disagree with the code:

| Half | Path | Language | Status |
| --- | --- | --- | --- |
| **Frontend** | `src/`, `index.html` | React 19 + TypeScript | A rich, fully-built UI |
| **Backend** | `backend/` | Python + FastAPI | Full REST API, DB, RBAC, ML |

**How connected are they today?**

- **Auth is real.** The login page calls the FastAPI backend over HTTP (`src/lib/api.ts` →
  `POST /api/v1/auth/login`), stores JWTs, and restores the session via `GET /api/v1/auth/me`.
- **Dashboard data is mocked.** The views (`Overview`, `Alerts`, `Behaviour`, `Timeline`,
  `Models`, `Settings`) all import their data from `src/data/mock.ts`. An API client for
  `/dashboard`, `/anomalies`, `/activity`, etc. **exists** in `src/lib/api.ts` but the views
  do not consume it yet.
- **The root `README.md` is stale.** It describes a "UI only, no ML runtime, dark-only" project
  from before the backend existed. The CSS is now **light-theme-first with a dark override**,
  navigation is a **sidebar + top bar** (not the top dropdown menus the README describes), and
  there absolutely *is* an ML runtime in `backend/ml/`.

> **Mental model:** the frontend is a *UI prototype wired to a real auth backend*, and the
> backend is a *complete, independently testable API + ML service* that the UI hasn't fully
> adopted yet. When the docs and the code disagree, trust the code.

---

## 3. Tech stack

### Frontend
| Concern | Choice |
| --- | --- |
| Framework | React **19** + TypeScript |
| Build | Vite **8** |
| Styling | Tailwind CSS **v4** (`@theme` design tokens) |
| Charts | Recharts **3** |
| Icons | lucide-react |
| Lint | oxlint |
| Types | `tsc -b` (part of `npm run build`) |

### Backend
| Concern | Choice |
| --- | --- |
| Framework | FastAPI |
| Server | Uvicorn |
| ORM | SQLAlchemy **2.x** |
| Validation | Pydantic **v2** + pydantic-settings |
| DB | PostgreSQL 15 |
| Migrations | Alembic |
| Auth | JWT (`python-jose`), bcrypt (`passlib`) |
| ML | scikit-learn, pandas, numpy, joblib |
| Tests | pytest + FastAPI TestClient |

### Infrastructure
- **Frontend hosting:** Vercel (`vercel.json`, SPA rewrite to `index.html`).
- **Backend hosting:** Docker / Cloud Run (`backend/Dockerfile`, `$PORT` aware).
- **Database:** Neon Postgres is configured for the project (`.neon`, `neon.ts`).
- **Local dev:** `backend/docker-compose.yml` (Postgres + API).

---

## 4. Repository layout

```
.
├─ index.html                # Vite entry, fonts, <div id="root">
├─ vite.config.ts            # react() + tailwindcss() plugins
├─ vercel.json               # static SPA deploy
├─ neon.ts / .neon           # Neon Postgres project config
├─ public/favicon.svg
│
├─ src/                      # ── FRONTEND ──────────────────────────────
│  ├─ main.tsx               # ReactDOM root: ThemeProvider > AuthProvider > App
│  ├─ App.tsx                # app shell, view routing, drawers, ⌘K search
│  ├─ index.css              # design tokens (@theme), dark overrides, keyframes
│  ├─ data/
│  │  ├─ types.ts            # frontend domain model
│  │  └─ mock.ts             # deterministic synthetic dataset (1025 lines)
│  ├─ lib/
│  │  ├─ api.ts              # typed fetch client + token mgmt + refresh
│  │  ├─ auth.tsx            # AuthContext / useAuth
│  │  ├─ theme.tsx           # ThemeContext / useTheme (light|dark|system)
│  │  ├─ nav.ts              # NAV_GROUPS, ViewId, breadcrumbs
│  │  └─ utils.ts            # cn(), formatting, risk tones, relative time
│  └─ components/
│     ├─ layout/             # Sidebar, TopBar, Logomark, PageHeader, PostureWidget
│     ├─ ui/                 # Panel, Badge, Avatar, Meter, RiskDial, Drawer, ...
│     ├─ charts/             # RiskTrendChart, BehaviourRadar, KindDonut, ...
│     ├─ lists/              # AlertRow, IdentityRow, EventFeed
│     ├─ detail/             # AlertDrawer, EmployeeDrawer
│     └─ views/              # LandingPage, LoginPage, Overview, Behaviour,
│                            #   Alerts, Timeline, Models, Settings
│
└─ backend/                  # ── BACKEND ──────────────────────────────
   ├─ app/
   │  ├─ main.py             # FastAPI app, lifespan, middleware, routers
   │  ├─ core/               # config, database, security, dependencies (RBAC)
   │  ├─ api/                # route modules (auth, dashboard, anomalies, ...)
   │  ├─ models/             # SQLAlchemy models
   │  ├─ schemas/            # Pydantic request/response schemas
   │  ├─ services/           # risk_service (signal → score)
   │  ├─ ml/                 # interface.py + adapter.py (mock detector)
   │  └─ utils/              # seed.py (dev seed), audit.py
   ├─ ml/                    # the REAL pipeline (own package)
   │  ├─ generate_dataset.py # synthetic data generator
   │  ├─ preprocess.py       # ColumnTransformer factory
   │  ├─ train.py            # train + compare + save .joblib
   │  ├─ inference.py        # MLService singleton (loads artifact)
   │  ├─ risk_engine.py      # weighted 0–100 risk score + severity
   │  ├─ rules.py            # 8 deterministic rules
   │  └─ artifacts/          # pipeline.joblib, metrics.json, CSVs
   ├─ alembic/               # migrations (001_initial_tables.py)
   ├─ tests/                 # pytest suite
   ├─ scripts/seed_data.py   # richer demo seed
   ├─ docker-compose.yml
   ├─ Dockerfile
   └─ setup.sh               # one-shot dev environment bootstrap
```

---

## 5. Getting it running

### Frontend only (fastest path to see the UI)

```bash
npm install
npm run dev                     # http://localhost:5173
```

`npm run dev` serves the UI. You can browse the Landing Page and all dashboard views
immediately, but **login requires the backend** because auth is a real API call.

### Full stack (backend + database + ML)

```bash
# Option A — Docker (recommended)
cd backend
docker compose up --build       # API :8000, Postgres :5432

# Option B — manual
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # set DATABASE_URL + JWT_SECRET
alembic upgrade head
python -m app.utils.seed        # demo users/roles/anomalies (or scripts/seed_data.py)
python ml/train.py              # generate data + train the model → ml/artifacts/
uvicorn app.main:app --reload   # http://localhost:8000
```

> There is also a `backend/setup.sh` that automates the whole manual flow (Postgres user/db
> creation, venv, migrations, seed). Read it before running — it uses `sudo` and creates a
> local Postgres role.

- API docs: `http://localhost:8000/docs` (Swagger) and `/redoc`.
- Health: `GET http://localhost:8000/health`.
- Demo login: `admin@sentinel.demo` / `Admin123!` (full list in §11).

### Useful scripts

| Command | Where | Does |
| --- | --- | --- |
| `npm run dev` | root | Vite dev server |
| `npm run build` | root | `tsc -b` typecheck + production bundle → `dist/` |
| `npm run lint` | root | oxlint |
| `python ml/train.py` | `backend/` | regenerate data + train + save artifacts |
| `pytest tests/ -v` | `backend/` | run backend test suite |

---

## 6. Domain model & vocabulary

There are **two type layers**. They share concepts but are not generated from one another —
know both.

### Frontend model — `src/data/types.ts`

- **`Severity`**: `critical | high | medium | low`
- **`AnomalyKind`**: the eight classes above (frontend uses snake_case, e.g.
  `off_hours_access`).
- **`AlertStatus`**: `new | investigating | contained | dismissed`
- **`BehaviourVector`** — the six axes on the employee radar:
  `accessVolume`, `offHours`, `resourceBreadth`, `privilegeUse`, `peerDeviation`,
  `geoVelocity`.
- **`Alert`** — a detection: `kind`, `severity`, `confidence`, `riskScore`, `headline`,
  `narrative`, `tactic` (MITRE-ish), `asset`, `sourceIp`, `geo`, `factors[]`, `detector`.
- **`Employee`** — a monitored identity: `riskScore`, signed `drift` (σ from baseline),
  `behaviour`, 24-slot `hourly[]`, `peerGroup`, `baselineShift[]`, `status`.
- Plus `TrendPoint`, `HeatCell`, `ActivityEvent`, `DetectorHealth`, `KindMeta`.

### Backend model — `backend/app/models/`

| Table | Purpose |
| --- | --- |
| `users`, `roles`, `user_roles` | accounts + many-to-many RBAC |
| `activities` | raw ingested behaviour events (`user_id`, `timestamp`, `event_type`, `action`, `resource`, `source_ip`, `device`, `location`, `application`, `metadata`, `risk_contribution`) |
| `anomalies` | detections (`detection_type`, `severity`, `risk_score`, `anomaly_score`, `confidence`, `status`, `detected_at`) |
| `risk_events` | **explainability rows**: `signal_type`, `signal_value`, `weight`, `contribution` per anomaly |
| `investigations`, `investigation_events` | case management + its audit trail |
| `detection_policies` | per-detector enable/threshold/severity config |
| `notifications` | user-facing alerts linked to anomalies |

Note backend `severity`/`status`/`detection_type` values are **UPPER_SNAKE** strings
(`CRITICAL`, `OPEN`, `OFF_HOURS_ACCESS`), whereas the frontend uses lowercase enums. Any future
wiring of the UI to the API must normalise these.

---

## 7. Frontend architecture

### Rendering flow — `src/main.tsx` → `src/App.tsx`

```
ThemeProvider (light|dark|system, persists to localStorage['sentinel_theme'])
└─ AuthProvider (restores session, exposes login/logout/user/loading/error)
   └─ App
```

`App.tsx` is the shell and the router-in-one-file:

1. **Landing page** — `showLanding` starts `true`; `LandingPage` renders until the user clicks
   "Enter Command Center".
2. **Login gate** — if there is no `user`, show the login spinner (while `loading`) or
   `LoginPage`.
3. **App shell** — `Sidebar` + `TopBar` + `<main>` view, with the two drawers rendered as
   siblings.

Views are **code-split** via `React.lazy` + `Suspense` (fallback `DashboardSkeleton`); only
`LandingPage` and `LoginPage` are eagerly loaded. This keeps the initial bundle small and defers
the Recharts chunk.

### Routing & navigation — `src/lib/nav.ts`

There is no router library. `ViewId` is a union (`overview | behaviour | alerts | timeline |
models | settings`) held in `App` state. `NAV_GROUPS` groups them into **Overview / Detection /
Behaviour / Intelligence**, each item carrying a label, icon, blurb and breadcrumb. Helpers:
`navItem(id)` and `findGroup(id)`.

The `Sidebar` renders single-item groups as direct links and multi-item groups as collapsible
sections that auto-expand to reveal the active item. It can collapse to a 60px icon rail.

### State & cross-linking

`App` owns the "which drawer is open" state (`alertId`, `employeeId`) and the global search
query. Drawers cross-link: opening an employee from an alert closes the alert drawer and
vice-versa. `⌘K` / `Ctrl+K` focuses the `TopBar` search; the query is passed down into
`Behaviour` and `Alerts` to filter rows client-side.

### Contexts

- **`lib/auth.tsx`** — `useAuth()`. On mount, if a token exists it calls `getMe()`; failure
  clears tokens. `login()` surfaces friendly errors via `getLoginErrorMessage()`.
- **`lib/theme.tsx`** — `useTheme()`. Toggles `.light`/`.dark` classes on `<html>`, persists to
  localStorage, listens for OS theme changes when set to `system`.

### API client — `src/lib/api.ts`

A single typed `apiFetch<T>()` wrapper:

- Prefixes `import.meta.env.VITE_API_URL || 'http://localhost:8000'`.
- Attaches `Authorization: Bearer <accessToken>` from a module-level variable seeded from
  localStorage.
- On **401** it attempts **one** silent refresh (`refreshAccessToken`, deduplicated via a shared
  promise), retries once, and on failure clears the session and redirects to `/login`.
- Exposes typed helpers: `login`, `logout`, `getMe`, `getDashboard`, `getUsers`,
  `getAnomalies`, `getActivity`, `getInvestigations`, `getPolicies`, `getMLStatus`, `mlPredict`,
  `checkHealth`, `getHealthDetail`.
- `ApiError` carries `status` + `code`; `getLoginErrorMessage()` maps status → human text and
  never leaks stack traces/SQL.

> ⚠️ This is the seam where the mock UI and the live backend meet. Wiring a view to real data
> means replacing its `from '../../data/mock'` import with an `apiFetch` call (and normalising
> the enum casing from §6).

### Styling & design system — `src/index.css`

Tailwind v4 with `@theme` tokens (no `tailwind.config.js` needed). **Light mode is the default
theme; dark is an override** on `.dark`.

- Semantic tokens: `bg`, `card`, `surface`/`-2`/`-3`, `border`/`-strong`, `text`/
  `-secondary`/`-muted`/`-faint`, `primary`(+`-text`/`-hover`), `hover`.
- Status tokens: `success`/`warning`/`critical`/`info` each with `-bg` and `-border`.
- Severity ramp: `sev-critical`/`sev-high`/`sev-medium`/`sev-low`.
- Fonts: **Inter** (sans) + **JetBrains Mono** (`num` class) loaded in `index.html`.
- Custom keyframes/animations: `fade-up`, `fade-in`, `slide-up`, `pulse-ring`, `ticker`,
  `menu-in`, `sidebar-in`.
- Components consume tokens via `var(--color-*)`; the `cn()` helper in `lib/utils.ts` merges
  classes.

When adding UI, **use tokens and existing primitives** (`Panel`, `Badge`, `Meter`, `RiskDial`,
`Segmented`, `Drawer`, `StatCard`, …) rather than ad-hoc hex colours.

---

## 8. Backend architecture

### App startup — `app/main.py`

The `lifespan` context runs on boot:

1. `Base.metadata.create_all(engine)` — dev convenience auto-migration (Alembic is the real
   mechanism).
2. `ml_service.load()` — loads `ml/artifacts/sentinel_ueba_pipeline.joblib`; logs a warning if
   the model hasn't been trained yet.

The app then registers **ten routers** and two middlewares:

- **Request metadata middleware** — assigns `X-Request-ID`, measures `X-Process-Time`, logs
  method/path/status/duration.
- **Security headers middleware** — `X-Content-Type-Options`, `X-Frame-Options: DENY`,
  `Referrer-Policy`, `X-XSS-Protection`.
- A **global exception handler** returns a generic 500 (`INTERNAL_SERVER_ERROR`) without leaking
  internals.
- CORS is driven by `settings.cors_origins_list` (parses a JSON string; safely falls back on bad
  input — see commit "Handle empty/missing CORS_ORIGINS env var gracefully").

Also exposes `GET /health` (checks DB with `SELECT 1` + ML loaded state) and `GET /`.

### Layering

```
api/       route handlers  →  Depends(get_db), Depends(require_*), RBAC
schemas/   Pydantic v2 request/response models (e.g. PolicyCreate → PolicyResponse)
models/    SQLAlchemy mapped classes
core/      config (Settings), database (engine/get_db), security (JWT/bcrypt), dependencies (RBAC)
services/  risk_service — signal list → normalised 0–100 score, creates risk_events
ml/adapter interface.py abstraction + MockAnomalyDetector (superseded by ml/ package)
utils/     seed.py, audit.py
```

`get_db()` is a generator dependency yielding a `SessionLocal`, closed in `finally`. Tests
override it globally.

### Core modules worth reading first

- **`core/config.py`** — `Settings(BaseSettings)` reading `.env`: `DATABASE_URL`, `JWT_SECRET`,
  `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `CORS_ORIGINS`,
  `ENVIRONMENT`, `REDIS_URL`.
- **`core/database.py`** — sync engine with `pool_pre_ping`, `pool_size=10`, `max_overflow=20`;
  `SessionLocal`; `Base(DeclarativeBase)`; `get_db()`.
- **`core/security.py`** — `hash_password`/`verify_password` (bcrypt), `create_access_token` /
  `create_refresh_token` (both embed `type`), `decode_token`, and `get_current_user` (validates
  token type `access`, loads the user, rejects non-`ACTIVE` accounts).
- **`core/dependencies.py`** — the RBAC matrix: `require_admin`,
  `require_security_manager`, `require_security_analyst`, and a generic `require_role(*roles)`
  factory. Each inspects `current_user.roles` and raises 403 on mismatch.
- **`services/risk_service.py`** — `DEFAULT_WEIGHTS` per signal type
  (`OFF_HOURS_ACCESS: 0.20`, `LATERAL_MOVEMENT: 0.18`, …); `compute_risk_score(signals)` returns
  a weighted mean ×100; `create_risk_events()` persists explainability rows.

> There is a deliberate parallel here: `app/services/risk_service.py` (DB-backed, weights for
> API-raised signals) and `ml/risk_engine.py` (ML-probability-driven, used by `/ml/predict`).
> They are different scorers for different paths — don't assume one calls the other.

---

## 9. The ML / detection pipeline

This lives in **`backend/ml/`** and is independent of the API layer. Run it from the `backend/`
directory.

```
generate_dataset.py  →  processed train/test CSVs
        ↓
preprocess.py        →  ColumnTransformer (impute → log → scale / one-hot)
        ↓
train.py             →  LogisticRegression vs RandomForest → best F1 → pipeline.joblib
        ↓
inference.py         →  MLService singleton loads the artifact at app startup
        ↓
risk_engine.py       →  weighted 0–100 score + severity + explanation
rules.py             →  8 deterministic signal rules
        ↓
api/ml.py            →  POST /api/v1/ml/predict  ·  GET /api/v1/ml/status
```

### 9.1 Synthetic data — `generate_dataset.py`
- 10,000 rows, **~8% positive class** (`insider_threat`), `SEED = 42` (fully reproducible),
  80/20 train/test split.
- `generate_normal()` and `generate_threat()` draw from different distributions — threats have
  higher off-hours ratio, more sensitive-file access, larger external transfers, more privilege
  changes, etc.
- Outputs `sentinel_ueba_processed_train.csv`, `..._test.csv`, `sentinel_ueba_synthetic_raw.csv`
  into `ml/artifacts/`.

### 9.2 Features — `preprocess.py`
- **20 numeric features**: `login_count_7d`, `failed_login_rate`, `off_hours_ratio`,
  `weekend_ratio`, `sensitive_file_access`, `external_transfer_mb`, `cloud_upload_mb`,
  `usb_event_count`, `privileged_access_count`, `privilege_change_count_30d`,
  `email_external_ratio`, `session_duration_mean_min`, `access_velocity_per_hour`,
  `remote_session_ratio`, `unusual_location_score`, `new_device_score`, `peer_deviation_score`,
  `dormant_account_days`, `after_hours_sensitive_access`, `asset_criticality`.
- **3 categorical**: `department`, `role`, `account_type`.
- Pipeline: median impute → `log1p` on skewed counts → `StandardScaler` for numerics; most-frequent
  impute → `OneHotEncoder(handle_unknown='ignore')` for categoricals.
- `validate_schema()` pre-flight check (required columns, `event_id` uniqueness, target ∈ {0,1},
  numeric coercion).

### 9.3 Training — `train.py`
- Fits preprocessing **on train only**, then trains both models.
- Metrics: precision, recall, F1, ROC-AUC, PR-AUC, FPR, confusion matrix.
- Selects best by **F1** (precision/recall balance chosen for security work), retrains on the
  full train set, extracts normalised feature importances (RF `feature_importances_` or LR
  `|coef_|`).
- Saves `pipeline.joblib` (preprocessor + model + metadata + importances + evaluation) and
  `model_metrics.json`.

### 9.4 Inference — `inference.py`
`MLService` is a module-level singleton. `load()` reads the joblib artifact;
`predict(features)` builds a one-row DataFrame, transforms, runs `predict_proba`, and returns
`anomaly_probability`, `predicted_class`, `confidence` (`|p−0.5|·2`), `model_version` and
**risk factors** (top feature importances with human-readable descriptions).

### 9.5 Risk scoring — `risk_engine.py`
Weighted blend (documented in the class docstring):

```
risk = 0.40·ML_probability + 0.30·behavioural_signals
     + 0.15·asset_criticality + 0.15·privilege_context      → clamped 0–100
```

Severity thresholds: **LOW 0–39 · MEDIUM 40–69 · HIGH 70–89 · CRITICAL 90–100**. It also
generates a plain-English `explanation` string naming the dominant signals.

### 9.6 Rules — `rules.py`
Eight deterministic rules map raw features to detection types, each returning
`{type, signal_value 0–1, weight, description, rule_fired}`:

| Rule | Fires when… |
| --- | --- |
| Off-hours | `off_hours_ratio > 0.40` (or >0.25 + after-hours sensitive >2) |
| Dormant revival | `dormant_account_days > 30 AND velocity > 10` |
| Privilege escalation | `privilege_change_count_30d > 2` (or >20 privileged accesses as non-privileged) |
| Resource snooping | `sensitive_file_access > 8` or `external_transfer_mb > 80` or `cloud_upload_mb > 50` |
| Peer deviation | `peer_deviation_score > 0.50` |
| Session anomaly | long + mostly-remote sessions, or `velocity > 30` |
| Impossible travel | `unusual_location_score > 0.60` |
| Lateral movement | `velocity > 25 AND privileged_access_count > 15` |

### 9.7 Prediction endpoint — `api/ml.py`
`POST /api/v1/ml/predict` (requires **SECURITY_ANALYST**) runs ML → rules → risk engine and
returns a combined response: `predicted_class`, `anomaly_probability`, `risk_score`, `severity`,
`confidence`, `model_version`, `risk_factors[]`, `rule_signals[]`, `explanation`. Returns **503**
if the model isn't loaded (i.e. `ml/train.py` hasn't been run).

> **Note on `app/ml/interface.py` + `app/ml/adapter.py`:** these define an `AnomalyDetector` ABC
> and a random `MockAnomalyDetector`. They predate the real `ml/` package — the honest
> "shape" for a pluggable detector, but the live path is `ml/inference.py`.

---

## 10. API reference

Base path: `/api/v1`. All endpoints except auth require a `Bearer` access token. Path params are
UUID strings.

### Auth — `/auth` (`app/api/auth.py`)
| Method | Path | Notes |
| --- | --- | --- |
| POST | `/auth/login` | email + password → access + refresh tokens + user |
| POST | `/auth/logout` | requires auth (no server-side revocation) |
| POST | `/auth/refresh` | body `{"refreshToken": "..."}`, validates token `type` |
| GET | `/auth/me` | current user info |

### Dashboard — `app/api/dashboard.py`
| Method | Path | Returns |
| --- | --- | --- |
| GET | `/dashboard` | `metrics` (open alerts, identities watched, anomalies detected, mean risk index, watchlist), 14-day `anomalyTrend`, `detectionMix`, top-10 `priorityTriage`, top-10 `behaviourDrift` |

### Users, Anomalies, Activity
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/users` | paginated; search/department filters |
| GET | `/users/{id}` | single user |
| GET | `/anomalies` | filters: severity, status, detection_type, user_id, min risk, date range; sort; includes `risk_factors[]` |
| GET | `/anomalies/{id}` | single anomaly + factors |
| PATCH | `/anomalies/{id}` | update (e.g. status) — SECURITY_ANALYST |
| GET | `/activity` | paginated activity events |

### Investigations — `app/api/investigations.py`
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/investigations` | filters status/priority/assigned_to, sort, paginated, includes events |
| GET | `/investigations/{id}` | single + full event trail |
| POST | `/investigations` | create (OPEN) + `CREATED` event — SECURITY_ANALYST |
| PATCH | `/investigations/{id}` | update + `UPDATED` event |
| POST | `/investigations/{id}/assign` | **SECURITY_MANAGER** |
| POST | `/investigations/{id}/resolve` | sets `RESOLVED` + `resolved_at` |

### Policies — `app/api/policies.py`
| Method | Path | Required role |
| --- | --- | --- |
| GET | `/policies`, `/policies/{id}` | any authenticated |
| POST | `/policies` | SECURITY_MANAGER |
| PUT | `/policies/{id}` | SECURITY_MANAGER |
| PATCH | `/policies/{id}/status` | SECURITY_MANAGER |
| DELETE | `/policies/{id}` | **ADMIN** |

### Notifications, Ingestion, ML
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/notifications` | list |
| PATCH | `/notifications/{id}/read` | mark one read |
| PATCH | `/notifications/read-all` | mark all read |
| POST | `/ingestion/activities` | batch ingest — **ADMIN** |
| POST | `/ingestion/csv` | CSV upload (validates required columns + user existence) — **ADMIN** |
| GET | `/ml/status` | `{loaded, model_name, model_version}` |
| POST | `/ml/predict` | SECURITY_ANALYST |

### Non-versioned
`GET /` (service info) and `GET /health` (`status`, `database`, `ml_model`).

> **Pagination shape:** list endpoints return
> `{ items, page, page_size, total, total_pages }`.

---

## 11. Auth, RBAC & security

### Roles
`ADMIN` · `SECURITY_MANAGER` · `SECURITY_ANALYST` · `VIEWER` — stored in the `roles` table,
linked through `user_roles`.

| Role | Can |
| --- | --- |
| **ADMIN** | everything; delete policies; ingest data |
| **SECURITY_MANAGER** | create/update/toggle policies; assign investigations |
| **SECURITY_ANALYST** | view anomalies, run ML predictions, manage investigations |
| **VIEWER** | read-only dashboard access |

### Token flow
1. `POST /auth/login` verifies bcrypt hash and account status, then issues an **access** token
   (30 min) and a **refresh** token (7 days), both JWTs signed with `JWT_SECRET` and tagged with
   `type`.
2. The client attaches the access token to every request.
3. On 401, the client refreshes once and retries; a second failure logs the user out.

### Demo credentials (development only)

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin@sentinel.demo` | `Admin123!` |
| Analyst | `sarah.chen@sentinel.demo` | `Analyst123!` |
| Manager | `james.wilson@sentinel.demo` / `manager@sentinel.demo` | `Manager123!` |
| Viewer | `viewer@sentinel.demo` | `Viewer123!` |

> Two seed scripts exist: `app/utils/seed.py` (the one the Dockerfile runs) and
> `scripts/seed_data.py` (richer set of monitored employees — Omar Haddad, Derek Hollis, etc.).
> The two differ slightly in emails/departments, so check which one you ran.

### Hardening already present
CORS allow-list, security headers, request IDs/timing, global 500 handler, IDOR-safe lookups,
audit trails on investigations (`investigation_events`), and explainability rows on anomalies
(`risk_events`).

### Known security trade-offs (documented in-code)
- Tokens are stored in **localStorage** — fine for an educational project, not for production
  (prefer HttpOnly cookies).
- `logout` does **not** revoke tokens server-side.
- Default `JWT_SECRET` / DB passwords in `config.py` are placeholders — always override via
  `.env`.

---

## 12. Environment variables

### Backend — `backend/.env` (template `backend/.env.example`)
```ini
DATABASE_URL=postgresql://sentinel:CHANGE_ME@localhost:5432/sentinel_db
JWT_SECRET=CHANGE_ME_TO_A_RANDOM_SECRET_KEY
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
ENVIRONMENT=development
```
Generate a real secret with `openssl rand -hex 32` (what `setup.sh` does).

### Frontend — `.env.local` (root)

There is no committed template for this one — the file only exists on your machine, so create
it yourself if you need to override the API URL:
```ini
VITE_API_URL=http://localhost:8000
```
If unset, `src/lib/api.ts` falls back to `http://localhost:8000`. `.env.local` is gitignored
(`*.local`) — never commit it.

---

## 13. Testing

### Backend — `backend/tests/` (pytest)
`conftest.py` sets up a **SQLite** test DB (`test.db`), overrides `get_db`, and recreates tables
per test. Fixtures give you `test_user`/`admin_user`, `analyst_token`/`admin_token`, and
`auth_headers`/`admin_headers`.

| File | Covers |
| --- | --- |
| `test_health.py` | `/health`, `/` |
| `test_auth.py` | login, refresh, `/me`, bad credentials |
| `test_rbac.py` | role enforcement across endpoints |
| `test_anomalies.py` | list/filter/update anomalies |
| `test_investigations.py` | full investigation lifecycle |
| `test_dashboard.py` | dashboard metrics shape |
| `test_ml.py` | ML service / prediction path |

Run: `cd backend && pytest tests/ -v`

> Tests import PostgreSQL-dialect `UUID` columns (`uuid.UUID` Python defaults) against SQLite —
> it works, but is a subtle spot if you add new model columns.

### Frontend
There is **no test runner configured** (`package.json` has no `test` script). The enforced
quality gates are `npm run build` (`tsc -b` typecheck + bundle) and `npm run lint` (oxlint).
Always run both after non-trivial changes.

---

## 14. Deployment

- **Frontend → Vercel.** `vercel.json` sets `framework: vite`, `buildCommand: npm run build`,
  `outputDirectory: dist`, and rewrites all paths to `/index.html` (SPA). Set `VITE_API_URL` in
  the Vercel project env to point at the deployed API.
- **Backend → Docker / Cloud Run.** `backend/Dockerfile` is a `python:3.11-slim` image that
  installs deps, then on start runs the idempotent seed (`python -m app.utils.seed`) and
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. It respects Cloud Run's injected `PORT`.
- **Database → Neon Postgres.** `.neon` holds org/project/branch ids; `neon.ts` is the
  `@neon/config` file. Set `DATABASE_URL` to the Neon connection string in the backend env.
- **Local/integration → docker-compose.** Spins up Postgres 15 with a healthcheck plus the API
  with hot reload.

---

## 15. Conventions, quirks & gotchas

**Conventions**
- Frontend: semantic CSS tokens (`bg-surface`, `text-muted`, `var(--color-*)`) — never raw hex in
  components. Reuse existing `ui/` primitives.
- Backend: keep the `models → schemas → api` separation; add a Pydantic schema for every request
  body; guard routes with the right `require_*` dependency.
- Comment the *why*, keep functions small, and mirror the existing docstring style (many modules
  open with a short triple-quoted summary).
- The ML package is meant to be runnable standalone: `python ml/train.py`, `python
  ml/generate_dataset.py`.

**Quirks / things that will bite you**
1. **README drift** — the root `README.md` describes an older, UI-only, dark-only version. Prefer
   this guide and the code.
2. **Mock vs. live data** — views read `src/data/mock.ts`; only auth hits the API. Don't assume a
   dashboard change is backed by the DB.
3. **Enum casing mismatch** — frontend lowercase (`off_hours_access`) vs backend UPPER_SNAKE
   (`OFF_HOURS_ACCESS`). Normalise at the API boundary.
4. **Two risk scorers** — `app/services/risk_service.py` vs `ml/risk_engine.py`. Pick the right
   one for the path you're on.
5. **Two seed scripts** with slightly different data (`app/utils/seed.py` vs
   `scripts/seed_data.py`).
6. **Two detector abstractions** — `app/ml/adapter.py` (mock) vs `ml/` (real). The live path is
   the latter.
7. **`/ml/predict` returns 503** until `python ml/train.py` has produced the joblib artifact.
8. **`docker-compose.yml` typo**: `ACCESS_TOKEN_EXPIME_MINUTES` (should be `..._EXPIRE_...`), so
   the container silently falls back to the 30-minute default.
9. **`conftest.py` typo**: `autofflush=False` (should be `autoflush`) — an ignored kwarg.
10. **`create_all()` on startup** is a dev convenience; schema changes should go through Alembic.
11. **`frontend has no test suite`** — lean on `npm run build` + lint for verification.
12. **`setup.sh` uses sudo** and creates a local Postgres role — read before running.

---

## 16. Suggested learning path

1. **See it.** `npm run dev`, click through the landing page and all six views. Note the design
   language and the two drawers.
2. **Read the shell.** `src/main.tsx` → `src/App.tsx` → `src/lib/nav.ts`. Understand view routing,
   lazy loading, and drawer state.
3. **Read the domain.** `src/data/types.ts`, then skim `src/data/mock.ts` to see what a synthetic
   dataset looks like.
4. **Trace auth.** `LoginPage` → `lib/auth.tsx` → `lib/api.ts` → `backend/app/api/auth.py` →
   `core/security.py`. This is the one fully-wired end-to-end flow.
5. **Boot the backend.** docker-compose, seed, hit `/docs`, log in with the demo admin, exercise
   `/dashboard`, `/anomalies`, `/investigations`.
6. **Understand RBAC.** `core/dependencies.py` + `tests/test_rbac.py`.
7. **Trace the ML path.** Run `python ml/train.py`, read its console output, then follow
   `api/ml.py` → `ml/inference.py` → `ml/risk_engine.py` → `ml/rules.py`.
8. **Read the data model.** The eight SQLAlchemy models, then the Alembic initial migration.
9. **Extend it (best way to learn):** wire one view (e.g. `Alerts`) to `getAnomalies()` with
   proper enum normalisation — that single exercise touches routing, API client, schemas, models
   and the two type systems.

---

## 17. Glossary

| Term | Meaning |
| --- | --- |
| **UEBA** | User & Entity Behaviour Analytics — detecting threats from behaviour, not signatures |
| **Identity / Employee** | A monitored person; the unit of risk |
| **Anomaly / Alert / Detection** | One suspicious behavioural finding |
| **Peer group** | The cohort an identity is baselined against |
| **Drift** | Signed deviation (in σ) from a baseline |
| **Risk score** | Composite 0–100 priority measure |
| **Severity** | Bucketed risk: LOW / MEDIUM / HIGH / CRITICAL |
| **Detection policy** | Per-detector enable/threshold/severity configuration |
| **Investigation** | A case opened against an anomaly, with an event trail |
| **Risk event** | Persisted explainability row (signal type/value/weight/contribution) |
| **Artifact** | The saved `pipeline.joblib` (preprocessor + model + metadata) |

---

*Last reviewed against the codebase: frontend React 19 / Vite 8 / Tailwind v4; backend FastAPI +
SQLAlchemy 2 + a scikit-learn pipeline over a synthetic dataset.*
