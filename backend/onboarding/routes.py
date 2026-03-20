from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db, Worker, Policy
from datetime import datetime, timedelta
import uuid, sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

router = APIRouter()

# ── SCHEMAS ──────────────────────────────────────────────────────────────────

class OnboardRequest(BaseModel):
    phone: str
    name: str = ""
    city: str
    zone_id: str
    zone_lat: float
    zone_lon: float
    platform: str            # blinkit / zepto / swiggy
    platform_segment: str    # grocery / food / ecommerce
    plan: str                # basic / standard / max
    upi_id: str
    avg_daily_earnings: float
    avg_deliveries_per_day: int
    avg_delivery_distance: float
    shift_start_hour: int = 9
    shift_end_hour: int = 21
    working_days: str = "0,1,2,3,4,5,6"
    language: str = "en"
    fcm_token: str = None

class GPSPingRequest(BaseModel):
    worker_id: str
    lat: float
    lon: float
    accuracy_m: float
    battery_pct: int = 100
    app_state: str = "foreground"

# ── CONSTANTS ────────────────────────────────────────────────────────────────

PLAN_CONFIG = {
    "basic":    {"daily": 1,  "weekly": 7,  "replacement": 0.40, "cap": 250},
    "standard": {"daily": 3,  "weekly": 21, "replacement": 0.60, "cap": 500},
    "max":      {"daily": 5,  "weekly": 35, "replacement": 0.80, "cap": 900},
}

SEGMENT_PER_DELIVERY_RANGE = {
    "grocery":   (12, 60),
    "food":      (18, 120),
    "ecommerce": (25, 150),
}

# ── ROUTES ───────────────────────────────────────────────────────────────────

@router.post("/register")
def register_worker(req: OnboardRequest, db: Session = Depends(get_db)):
    # Validate plan
    if req.plan not in PLAN_CONFIG:
        raise HTTPException(400, f"Invalid plan. Choose from: {list(PLAN_CONFIG.keys())}")

    # Validate earnings plausibility
    per_delivery = req.avg_daily_earnings / max(req.avg_deliveries_per_day, 1)
    low, high = SEGMENT_PER_DELIVERY_RANGE.get(req.platform_segment, (10, 200))
    if not (low <= per_delivery <= high):
        raise HTTPException(400, {
            "error": "earnings_implausible",
            "detail": f"Per-delivery value ₹{per_delivery:.0f} is outside expected range ₹{low}–₹{high} for {req.platform_segment}",
            "hint": "Please re-check your average deliveries per day"
        })

    # Check duplicate
    existing = db.query(Worker).filter(Worker.phone == req.phone).first()
    if existing:
        raise HTTPException(409, {"error": "phone_already_registered", "worker_id": existing.worker_id})

    worker_id = f"WRK_{uuid.uuid4().hex[:10].upper()}"

    # Compute initial risk multiplier (rule-based for Phase 1)
    try:
        from ..ml.risk_model.predict import get_risk_multiplier
        risk_mult = get_risk_multiplier({
            "city": req.city, "shift": "day" if req.shift_start_hour < 18 else "night",
            "avg_daily_earnings": req.avg_daily_earnings, "weeks_on_platform": 0,
            "claims_last_4_weeks": 0, "zone_disruption_freq": 0.3,
            "season": _current_season(), "is_multi_platform": 0
        })
    except Exception:
        risk_mult = 1.0

    cfg = PLAN_CONFIG[req.plan]
    base_premium = cfg["weekly"]
    final_premium = round(base_premium * risk_mult, 2)

    # Create worker
    worker = Worker(
        worker_id=worker_id,
        phone=req.phone,
        name=req.name,
        city=req.city,
        zone_id=req.zone_id,
        zone_lat=req.zone_lat,
        zone_lon=req.zone_lon,
        platform=req.platform,
        platform_segment=req.platform_segment,
        plan=req.plan,
        upi_id=req.upi_id,
        fcm_token=req.fcm_token,
        avg_daily_earnings=req.avg_daily_earnings,
        avg_deliveries_per_day=req.avg_deliveries_per_day,
        avg_delivery_distance=req.avg_delivery_distance,
        shift_start_hour=req.shift_start_hour,
        shift_end_hour=req.shift_end_hour,
        working_days=req.working_days,
        language=req.language,
        reliability_score=0.5,
    )
    db.add(worker)

    # Create policy (valid Mon–Sun this week)
    now = datetime.utcnow()
    week_start = now - timedelta(days=now.weekday())
    week_end   = week_start + timedelta(days=7)
    policy = Policy(
        policy_id=f"POL_{uuid.uuid4().hex[:10].upper()}",
        worker_id=worker_id,
        plan=req.plan,
        weekly_premium=final_premium,
        risk_multiplier=risk_mult,
        income_replacement_pct=cfg["replacement"],
        weekly_cap=cfg["cap"],
        valid_from=week_start,
        valid_until=week_end,
        active=True,
    )
    db.add(policy)
    db.commit()

    return {
        "success": True,
        "worker_id": worker_id,
        "policy_id": policy.policy_id,
        "plan": req.plan,
        "weekly_premium": final_premium,
        "risk_multiplier": risk_mult,
        "weekly_cap": cfg["cap"],
        "income_replacement_pct": cfg["replacement"],
        "message": f"Welcome to ShieldShift, {req.name or 'Partner'}! Your {req.plan} plan is active.",
        "policy_valid_until": week_end.isoformat()
    }


@router.get("/worker/{worker_id}")
def get_worker(worker_id: str, db: Session = Depends(get_db)):
    worker = db.query(Worker).filter(Worker.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(404, "Worker not found")
    policy = db.query(Policy).filter(
        Policy.worker_id == worker_id, Policy.active == True
    ).order_by(Policy.created_at.desc()).first()
    return {
        "worker_id": worker.worker_id,
        "name": worker.name,
        "city": worker.city,
        "zone_id": worker.zone_id,
        "platform": worker.platform,
        "plan": worker.plan,
        "upi_id": worker.upi_id,
        "avg_daily_earnings": worker.avg_daily_earnings,
        "policy": {
            "policy_id": policy.policy_id if policy else None,
            "weekly_premium": policy.weekly_premium if policy else None,
            "weekly_cap": policy.weekly_cap if policy else None,
            "valid_until": policy.valid_until.isoformat() if policy else None,
            "active": policy.active if policy else False,
        }
    }


@router.post("/gps/ping")
def record_gps_ping(ping: GPSPingRequest, db: Session = Depends(get_db)):
    from database import GPSPing
    if ping.accuracy_m > 200:
        return {"stored": False, "reason": "accuracy_too_low"}
    gps = GPSPing(
        worker_id=ping.worker_id, lat=ping.lat, lon=ping.lon,
        accuracy_m=ping.accuracy_m, battery_pct=ping.battery_pct,
        app_state=ping.app_state
    )
    db.add(gps)
    # Update last_active
    db.query(Worker).filter(Worker.worker_id == ping.worker_id).update(
        {"last_active": datetime.utcnow()}
    )
    db.commit()
    return {"stored": True, "timestamp": datetime.utcnow().isoformat()}


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _current_season():
    m = datetime.utcnow().month
    return {12:1,1:1,2:1, 3:2,4:2,5:2, 6:3,7:3,8:3,9:3, 10:4,11:4}.get(m, 3)
