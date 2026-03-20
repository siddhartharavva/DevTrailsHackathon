# ShieldShift — Architecture Documentation

## System Overview

ShieldShift is a microservices-style monorepo split into four layers:

```
[Worker PWA] ──→ [FastAPI Backend] ──→ [PostgreSQL / SQLite]
                       ↕                       ↕
               [ML Engine (Python)]    [Redis Cache]
                       ↕
               [Mock APIs (Express)] ──→ [Open-Meteo / CPCB]
```

---

## Backend Services

### Onboarding Service (`/backend/onboarding/`)
- `POST /api/onboarding/register` — Worker registration + policy creation
- `GET  /api/onboarding/worker/:id` — Fetch worker profile
- `POST /api/onboarding/gps/ping` — Record GPS location ping

### Trigger Engine (`/backend/trigger_engine/`)
- `POST /api/triggers/check-weather` — Poll Open-Meteo and fire triggers
- `POST /api/triggers/fire` — Manually fire a trigger (admin/demo)
- `GET  /api/triggers/events` — List all disruption events
- `GET  /api/triggers/eligibility/:worker/:event` — Run 3-gate eligibility check

### Claims Service (`/backend/claims/`)
- `POST /api/claims/process` — Trigger payout pipeline for a worker+event
- `GET  /api/claims/worker/:id` — Worker's claim history
- `GET  /api/claims/worker/:id/summary` — Weekly summary (saved vs lost)
- `GET  /api/claims/:claim_id` — Single claim detail

### Admin Service (`/backend/admin/`)
- `GET  /api/admin/dashboard` — Platform overview metrics
- `GET  /api/admin/claims/flagged` — Flagged/reviewed claims
- `GET  /api/admin/workers` — All registered workers
- `POST /api/admin/claims/:id/approve` — Manual claim approval

---

## ML Models

### Model 1 — Risk Regressor (XGBoost)
- **File:** `ml/risk_model/train.py`
- **Input:** 11 worker/context features
- **Output:** Risk multiplier 0.7–1.5
- **Used in:** Premium calculation at onboarding + weekly repricing

### Model 2 — Payout Regressor (XGBoost)
- **File:** `ml/payout_model/train.py`
- **Input:** 9 worker/event features
- **Output:** Compensation amount in ₹
- **Used in:** Claims payout calculation
- **Phase 1 fallback:** Transparent formula (same output shape)

### Model 3 — Fraud Detector (Isolation Forest)
- **File:** `ml/fraud_detection/train.py`
- **Input:** 6 behavioural features
- **Output:** Anomaly score 0.0–1.0
- **Used in:** Claims pipeline before payout execution
- **GPS spoofing check:** `check_gps_spoofing()` — 3 signal checks

---

## Mock APIs (Port 4000)

| Endpoint | Simulates |
|---|---|
| `GET /curfew/events` | Municipal gazette curfew orders |
| `POST /curfew/fire` | Issue a new curfew event |
| `GET /platform/zone-status` | Blinkit/Zepto order volume |
| `GET /platform/order-volume/:zone` | Hourly volume history |
| `POST /registry/verify` | e-Shram worker ID lookup |

---

## Data Flow — Event to Payout

```
1. Open-Meteo API / Mock curfew API
         ↓
2. Trigger Engine detects threshold breach
         ↓
3. DisruptionEvent written to DB
         ↓
4. Background task: find all active workers in zone
         ↓  (for each worker, in parallel)
5. Gate 1: Shift profile check  (DB lookup)
5. Gate 2: GPS zone presence    (GPS pings table)
5. Gate 3: Population cross-check (aggregate GPS pings)
         ↓
6. Isolation Forest anomaly score
         ↓
7. Payout amount calculated (formula / ML model)
         ↓
8. Weekly cap check (sum of prior claims this week)
         ↓
9. Razorpay Payouts API (sandbox / demo mock)
         ↓
10. Twilio SMS + FCM push notification
         ↓
11. Claim record written (immutable audit log)
```

---

## Anti-Spoofing Architecture

Three layers of GPS spoofing detection in `ml/fraud_detection/train.py`:

1. **Perfect accuracy flag** — Spoofing apps report < 3m accuracy; genuine GPS in rain degrades to 80–200m
2. **Location teleport** — > 3 km jump between consecutive 10-min pings
3. **Uniform timing** — Std deviation of ping intervals < 2 seconds (spoofing apps clock precisely)

Ring detection in `backend/trigger_engine/routes.py`:
- **Temporal clustering** — > 80% of claims within 4-minute window
- **Population cross-check** — Minimum 30–50% zone worker inactivity required
- **Liquidity circuit breaker** — Total outflow > 2.5× statistical expectation triggers hold
