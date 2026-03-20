# ShieldShift — Quick Start Guide

## Prerequisites
- Python 3.10+
- Node.js 18+
- Git

## 1. Clone & Setup

```bash
git clone https://github.com/your-team/shieldshift
cd shieldshift
cp .env.example .env
# Edit .env — DEMO_MODE=true is set by default (no real API keys needed)
```

## 2. Install Dependencies

```bash
# Python backend
pip install -r backend/requirements.txt

# Node (mock APIs + frontend)
cd mock_apis && npm install && cd ..
cd frontend  && npm install && cd ..
```

## 3. Train ML Models

```bash
cd ml
python train_all.py
# Generates synthetic data + trains all 3 models in ~60 seconds
cd ..
```

## 4. Run All Services

Open 3 terminals:

**Terminal 1 — Backend API (port 8000)**
```bash
cd backend
python -c "from database import init_db; init_db()"  # create tables
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Mock APIs (port 4000)**
```bash
cd mock_apis
node server.js
```

**Terminal 3 — Frontend (port 5173)**
```bash
cd frontend
npm run dev
```

## 5. Open the App

- **Worker app:** http://localhost:5173
- **API docs:**   http://localhost:8000/docs  (Swagger UI — interactive)
- **Mock APIs:**  http://localhost:4000

## 6. Demo Walkthrough

### Onboard a worker
1. Open http://localhost:5173
2. Select language → Blinkit → Bengaluru → ₹520 earnings / 22 deliveries → Standard plan
3. Enter any phone number (e.g. 9876543210) and UPI ID (e.g. test@upi)
4. Click "Activate Policy" — worker is registered, policy created

### Fire a trigger and watch the payout
1. Navigate to Admin (⚙️ tab) → Trigger panel
2. Select "Heavy Rain" → Zone "Bengaluru South" → Duration 4h
3. Click "🚨 Fire Trigger & Process Payouts"
4. Wait ~5 seconds
5. Navigate to Dashboard — you'll see the payout credited
6. Navigate to Claims — the claim record shows the full breakdown

### View fraud detection
1. Admin → Fraud tab
2. Any workers with anomaly score > 0.3 appear here

## Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `DEMO_MODE` | `true` | Simulates all payments — no Razorpay key needed |
| `DATABASE_URL` | SQLite | No setup needed for development |
| `RAZORPAY_KEY_ID` | — | Only needed if DEMO_MODE=false |
| `TWILIO_ACCOUNT_SID` | — | Only needed if DEMO_MODE=false |

## API Documentation

Full interactive docs available at http://localhost:8000/docs (Swagger UI)

Key endpoints for the demo:
- `POST /api/onboarding/register` — Register a worker
- `POST /api/triggers/fire` — Fire a manual trigger (demo)
- `GET  /api/claims/worker/{id}/summary` — Worker's weekly summary
- `GET  /api/admin/dashboard` — Platform metrics
