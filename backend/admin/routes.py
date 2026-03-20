from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db, Worker, Claim, DisruptionEvent
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    """Main admin dashboard — overview of platform health."""
    now = datetime.utcnow()
    week_start = now - timedelta(days=now.weekday())

    total_workers   = db.query(Worker).count()
    active_policies = db.query(Worker).filter(Worker.policy_active == True).count()
    total_claims    = db.query(Claim).count()
    week_claims     = db.query(Claim).filter(Claim.created_at >= week_start).count()
    week_payout     = db.query(func.sum(Claim.amount)).filter(
        Claim.created_at >= week_start, Claim.status == "success"
    ).scalar() or 0
    flagged = db.query(Claim).filter(
        Claim.status.in_(["manual_review", "rejected"])
    ).count()
    auto_approved = db.query(Claim).filter(Claim.status == "success").count()
    active_events = db.query(DisruptionEvent).filter(DisruptionEvent.active == True).all()

    return {
        "total_workers": total_workers,
        "active_policies": active_policies,
        "total_claims": total_claims,
        "week_claims": week_claims,
        "week_payout_inr": round(float(week_payout), 2),
        "flagged_claims": flagged,
        "auto_approved_claims": auto_approved,
        "fraud_rate": round(flagged / max(total_claims, 1), 3),
        "active_events": [_event_dict(e) for e in active_events],
    }

@router.get("/claims/flagged")
def get_flagged_claims(db: Session = Depends(get_db)):
    claims = db.query(Claim).filter(
        Claim.status.in_(["manual_review", "rejected"])
    ).order_by(Claim.created_at.desc()).limit(50).all()
    result = []
    for c in claims:
        worker = db.query(Worker).filter(Worker.worker_id == c.worker_id).first()
        result.append({
            "claim_id": c.claim_id,
            "worker_id": c.worker_id,
            "worker_city": worker.city if worker else "unknown",
            "event_id": c.event_id,
            "amount": c.amount,
            "status": c.status,
            "anomaly_score": c.anomaly_score,
            "failure_reason": c.failure_reason,
            "gps_confidence": c.gps_confidence,
            "created_at": c.created_at.isoformat(),
        })
    return result

@router.get("/workers")
def list_workers(db: Session = Depends(get_db)):
    workers = db.query(Worker).order_by(Worker.created_at.desc()).limit(100).all()
    return [_worker_dict(w) for w in workers]

@router.get("/events")
def list_events(db: Session = Depends(get_db)):
    events = db.query(DisruptionEvent).order_by(
        DisruptionEvent.created_at.desc()
    ).limit(50).all()
    return [_event_dict(e) for e in events]

@router.post("/events/{event_id}/resolve")
def resolve_event(event_id: str, db: Session = Depends(get_db)):
    db.query(DisruptionEvent).filter(DisruptionEvent.event_id == event_id).update({
        "active": False, "end_time": datetime.utcnow()
    })
    db.commit()
    return {"resolved": True, "event_id": event_id}

@router.post("/claims/{claim_id}/approve")
def manual_approve(claim_id: str, db: Session = Depends(get_db)):
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        from fastapi import HTTPException
        raise HTTPException(404, "Claim not found")
    worker = db.query(Worker).filter(Worker.worker_id == claim.worker_id).first()
    db.query(Claim).filter(Claim.claim_id == claim_id).update({"status": "success",
        "settled_at": datetime.utcnow(), "utr": f"MANUAL_{claim_id[:8]}"})
    db.commit()
    return {"approved": True, "claim_id": claim_id}

def _event_dict(e):
    return {"event_id": e.event_id, "trigger_type": e.trigger_type, "severity": e.severity,
            "zone_id": e.zone_id, "city": e.city, "description": e.description,
            "active": e.active, "start_time": e.start_time.isoformat()}

def _worker_dict(w):
    return {"worker_id": w.worker_id, "name": w.name, "city": w.city,
            "platform": w.platform, "plan": w.plan, "policy_active": w.policy_active,
            "avg_daily_earnings": w.avg_daily_earnings, "claims_last_4_weeks": w.claims_last_4_weeks,
            "reliability_score": w.reliability_score, "created_at": w.created_at.isoformat()}
