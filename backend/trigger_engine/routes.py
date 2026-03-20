from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db, Worker, DisruptionEvent, GPSPing, Policy
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
import uuid, requests, os

router = APIRouter()

# ── TRIGGER THRESHOLDS ───────────────────────────────────────────────────────

WEATHER_TRIGGERS = {
    "RAIN_HEAVY":   {"field": "precipitation", "threshold": 35,    "severity": "orange"},
    "RAIN_EXTREME": {"field": "precipitation", "threshold": 64.5,  "severity": "red"},
    "HEAT_EXTREME": {"field": "temperature",   "threshold": 43,    "severity": "red"},
    "FLOOD":        {"field": "weathercode",   "threshold": 95,    "severity": "red"},
}

AQI_TRIGGERS = {
    "AQI_SEVERE":     {"threshold": 300, "severity": "orange"},
    "AQI_HAZARDOUS":  {"threshold": 400, "severity": "red"},
}

SEVERITY_INACTIVE_THRESHOLD = {"red": 0.50, "orange": 0.35, "yellow": 0.20}
SEVERITY_PAYOUT_FACTOR      = {"red": 1.0,  "orange": 0.75, "yellow": 0.50}

CITY_COORDS = {
    "bengaluru": (12.9716, 77.5946),
    "mumbai":    (19.0760, 72.8777),
    "delhi":     (28.6139, 77.2090),
    "hyderabad": (17.3850, 78.4867),
    "chennai":   (13.0827, 80.2707),
    "kolkata":   (22.5726, 88.3639),
    "pune":      (18.5204, 73.8567),
}

# ── SCHEMAS ──────────────────────────────────────────────────────────────────

class ManualTriggerRequest(BaseModel):
    trigger_type: str   # RAIN_HEAVY / AQI_SEVERE / CIVIC_CURFEW etc.
    severity: str       # red / orange / yellow
    zone_id: str
    city: str
    description: str
    raw_value: float = 0.0
    duration_hours: float = 4.0

class CheckEventRequest(BaseModel):
    city: str
    zone_id: str

# ── ROUTES ───────────────────────────────────────────────────────────────────

@router.post("/check-weather")
def check_weather_now(req: CheckEventRequest, db: Session = Depends(get_db)):
    """Poll Open-Meteo for current conditions and fire triggers if thresholds exceeded."""
    lat, lon = CITY_COORDS.get(req.city.lower(), (12.9716, 77.5946))
    weather = _fetch_open_meteo(lat, lon)
    if not weather:
        return {"error": "weather_fetch_failed"}

    triggered = []
    for trigger_id, cfg in WEATHER_TRIGGERS.items():
        val = weather.get(cfg["field"], 0)
        if val and val >= cfg["threshold"]:
            event = _create_event(
                db, trigger_id, cfg["severity"], req.zone_id, req.city,
                lat, lon, f"{trigger_id}: {val} detected", val
            )
            triggered.append({"trigger": trigger_id, "value": val, "event_id": event.event_id})

    return {"city": req.city, "weather": weather, "triggered": triggered}


@router.post("/fire")
def fire_manual_trigger(
    req: ManualTriggerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Admin endpoint — fire a manual trigger for demo / testing purposes."""
    lat, lon = CITY_COORDS.get(req.city.lower(), (12.9716, 77.5946))
    event = _create_event(
        db, req.trigger_type, req.severity, req.zone_id, req.city,
        lat, lon, req.description, req.raw_value,
        end_offset_hours=req.duration_hours
    )

    # Run payout pipeline in background for all eligible workers
    background_tasks.add_task(_run_zone_payouts, event.event_id)

    return {
        "success": True,
        "event_id": event.event_id,
        "trigger_type": req.trigger_type,
        "severity": req.severity,
        "zone_id": req.zone_id,
        "message": f"Event fired. Processing payouts for eligible workers in {req.zone_id}."
    }


@router.get("/events")
def list_events(db: Session = Depends(get_db)):
    events = db.query(DisruptionEvent).order_by(DisruptionEvent.created_at.desc()).limit(20).all()
    return [_event_to_dict(e) for e in events]


@router.get("/events/{event_id}")
def get_event(event_id: str, db: Session = Depends(get_db)):
    event = db.query(DisruptionEvent).filter(DisruptionEvent.event_id == event_id).first()
    if not event:
        from fastapi import HTTPException
        raise HTTPException(404, "Event not found")
    return _event_to_dict(event)


@router.get("/eligibility/{worker_id}/{event_id}")
def check_eligibility(worker_id: str, event_id: str, db: Session = Depends(get_db)):
    """Run full 3-gate eligibility check for a worker against an event."""
    worker = db.query(Worker).filter(Worker.worker_id == worker_id).first()
    event  = db.query(DisruptionEvent).filter(DisruptionEvent.event_id == event_id).first()
    if not worker or not event:
        from fastapi import HTTPException
        raise HTTPException(404, "Worker or event not found")
    return run_full_eligibility(worker, event, db)


# ── ELIGIBILITY ENGINE ───────────────────────────────────────────────────────

def run_full_eligibility(worker, event, db):
    shift_check = _check_shift(worker, event)
    zone_check  = _check_zone(worker.worker_id, event, db)
    pop_check   = _check_population(event, db)

    if not shift_check["pass"]:
        return {"eligible": False, "payout_factor": 0.0,
                "rejection_reason": shift_check["reason"], "shift_check": shift_check}

    if zone_check["pass"] is False:
        return {"eligible": False, "payout_factor": 0.0,
                "rejection_reason": zone_check["reason"], "zone_check": zone_check}

    if pop_check["verdict"] == "likely_fraud":
        return {"eligible": False, "payout_factor": 0.0,
                "rejection_reason": "population_signal_failed", "population_check": pop_check}

    severity_factor = SEVERITY_PAYOUT_FACTOR.get(event.severity, 0.5)
    combined = shift_check["payout_factor"] * zone_check.get("payout_factor", 1.0) * severity_factor
    needs_review = zone_check["pass"] == "partial" or pop_check["verdict"] == "manual_review"

    return {
        "eligible": True,
        "needs_review": needs_review,
        "payout_factor": round(combined, 3),
        "shift_check": shift_check,
        "zone_check": zone_check,
        "population_check": pop_check,
    }


def _check_shift(worker, event):
    event_start = event.start_time
    event_end   = event.end_time or (event.start_time + timedelta(hours=4))
    weekday     = event_start.weekday()
    working_days = [int(d) for d in worker.working_days.split(",")]

    if weekday not in working_days:
        return {"pass": False, "reason": "not_scheduled", "payout_factor": 0.0,
                "detail": f"Worker not scheduled on {event_start.strftime('%A')}"}

    shift_start = event_start.replace(hour=worker.shift_start_hour, minute=0, second=0)
    shift_end   = event_start.replace(hour=worker.shift_end_hour,   minute=0, second=0)
    overlap_s   = max(event_start, shift_start)
    overlap_e   = min(event_end,   shift_end)

    if overlap_s >= overlap_e:
        return {"pass": False, "reason": "no_shift_overlap", "payout_factor": 0.0,
                "detail": f"Event outside shift window ({worker.shift_start_hour}:00–{worker.shift_end_hour}:00)"}

    overlap_hours = (overlap_e - overlap_s).seconds / 3600
    shift_hours   = worker.shift_end_hour - worker.shift_start_hour
    factor        = min(overlap_hours / shift_hours, 1.0)

    return {"pass": True, "reason": "shift_overlap_confirmed",
            "overlap_hours": round(overlap_hours, 2), "shift_hours": shift_hours,
            "payout_factor": round(factor, 3), "detail": f"{overlap_hours:.1f}h of {shift_hours}h shift disrupted"}


def _check_zone(worker_id, event, db):
    lookback = event.start_time - timedelta(hours=2)
    ping = db.query(GPSPing).filter(
        GPSPing.worker_id == worker_id,
        GPSPing.timestamp >= lookback,
        GPSPing.timestamp <= event.start_time
    ).order_by(GPSPing.timestamp.desc()).first()

    if not ping:
        return {"pass": "partial", "reason": "no_recent_gps", "confidence": 0.4, "payout_factor": 0.6,
                "detail": "No GPS ping in 2h before event — payout reduced"}

    dist_km = _haversine(ping.lat, ping.lon, event.zone_center_lat, event.zone_center_lon)
    in_zone = dist_km <= 5.0
    minutes_before = int((event.start_time - ping.timestamp).seconds / 60)
    confidence = 1.0 if minutes_before < 30 else (0.85 if minutes_before < 60 else 0.7)

    # Anti-spoofing: flag suspiciously perfect GPS accuracy
    spoofing_flag = ping.accuracy_m < 3.0

    if in_zone:
        return {"pass": True, "reason": "gps_in_zone",
                "last_ping_minutes_before": minutes_before,
                "distance_km": round(dist_km, 2), "confidence": confidence,
                "payout_factor": confidence,
                "spoofing_flag": spoofing_flag,
                "detail": f"GPS ping {minutes_before}min before event, {dist_km:.1f}km from zone"}
    return {"pass": False, "reason": "gps_outside_zone",
            "distance_km": round(dist_km, 2), "confidence": 0.0, "payout_factor": 0.0,
            "detail": f"Last GPS ping {dist_km:.1f}km from disrupted zone"}


def _check_population(event, db):
    active_workers = db.query(Worker).filter(
        Worker.zone_id == event.zone_id,
        Worker.last_active >= datetime.utcnow() - timedelta(days=7),
        Worker.policy_active == True
    ).all()
    total = len(active_workers)

    if total < 5:
        return {"pass": "manual_review", "verdict": "manual_review",
                "reason": "insufficient_population", "total_zone_workers": total}

    inactive = 0
    for w in active_workers:
        ping = db.query(GPSPing).filter(
            GPSPing.worker_id == w.worker_id,
            GPSPing.timestamp >= event.start_time,
            GPSPing.timestamp <= (event.end_time or event.start_time + timedelta(hours=4))
        ).first()
        if not ping:
            inactive += 1

    rate = inactive / total
    t = SEVERITY_INACTIVE_THRESHOLD.get(event.severity, 0.20)
    verdict = "auto_approve" if rate >= t else ("manual_review" if rate >= t * 0.6 else "likely_fraud")

    return {
        "pass": verdict == "auto_approve",
        "verdict": verdict,
        "zone_inactive_rate": round(rate, 3),
        "inactive_workers": inactive,
        "total_zone_workers": total,
        "threshold": t,
        "detail": f"{rate*100:.0f}% of zone workers inactive ({inactive}/{total})"
    }


# ── PAYOUT PIPELINE ──────────────────────────────────────────────────────────

def _run_zone_payouts(event_id: str):
    """Background task: process payouts for all eligible workers in a zone."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        event = db.query(DisruptionEvent).filter(DisruptionEvent.event_id == event_id).first()
        if not event:
            return
        workers = db.query(Worker).filter(
            Worker.zone_id == event.zone_id,
            Worker.policy_active == True,
            Worker.last_active >= datetime.utcnow() - timedelta(days=3)
        ).all()
        from claims.payout_service import run_payout_pipeline
        for worker in workers:
            try:
                run_payout_pipeline(worker.worker_id, event_id, db)
            except Exception as e:
                print(f"Payout error for {worker.worker_id}: {e}")
    finally:
        db.close()


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _fetch_open_meteo(lat, lon):
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        r = requests.get(url, params={
            "latitude": lat, "longitude": lon,
            "current": ["precipitation", "temperature_2m", "windspeed_10m", "weathercode"],
            "timezone": "Asia/Kolkata"
        }, timeout=5)
        data = r.json().get("current", {})
        return {
            "precipitation": data.get("precipitation", 0),
            "temperature":   data.get("temperature_2m", 0),
            "wind_kph":      data.get("windspeed_10m", 0),
            "weathercode":   data.get("weathercode", 0),
        }
    except Exception:
        return None


def _create_event(db, trigger_type, severity, zone_id, city, lat, lon, desc, raw_value, end_offset_hours=4.0):
    now = datetime.utcnow()
    event = DisruptionEvent(
        event_id=f"EVT_{uuid.uuid4().hex[:10].upper()}",
        trigger_type=trigger_type,
        severity=severity,
        zone_id=zone_id,
        zone_center_lat=lat,
        zone_center_lon=lon,
        city=city,
        description=desc,
        raw_value=raw_value,
        start_time=now,
        end_time=now + timedelta(hours=end_offset_hours),
        active=True,
        source="open_meteo" if "RAIN" in trigger_type or "HEAT" in trigger_type else "mock"
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371
    d = lambda x: radians(x)
    a = sin((d(lat2)-d(lat1))/2)**2 + cos(d(lat1))*cos(d(lat2))*sin((d(lon2)-d(lon1))/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def _event_to_dict(e):
    return {
        "event_id": e.event_id, "trigger_type": e.trigger_type, "severity": e.severity,
        "zone_id": e.zone_id, "city": e.city, "description": e.description,
        "raw_value": e.raw_value, "start_time": e.start_time.isoformat(),
        "end_time": e.end_time.isoformat() if e.end_time else None,
        "active": e.active, "source": e.source,
    }
