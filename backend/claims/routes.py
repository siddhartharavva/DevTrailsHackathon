from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db, Claim, Worker
from datetime import datetime, timedelta

router = APIRouter()

class ManualPayoutRequest(BaseModel):
    worker_id: str
    event_id: str

@router.post("/process")
def trigger_payout(req: ManualPayoutRequest, background_tasks: BackgroundTasks,
                   db: Session = Depends(get_db)):
    background_tasks.add_task(_run, req.worker_id, req.event_id)
    return {"message": "Payout pipeline started", "worker_id": req.worker_id,
            "event_id": req.event_id}

@router.get("/worker/{worker_id}")
def get_worker_claims(worker_id: str, db: Session = Depends(get_db)):
    claims = db.query(Claim).filter(Claim.worker_id == worker_id)\
                            .order_by(Claim.created_at.desc()).limit(20).all()
    return [_claim_dict(c) for c in claims]

@router.get("/worker/{worker_id}/summary")
def get_worker_summary(worker_id: str, db: Session = Depends(get_db)):
    worker = db.query(Worker).filter(Worker.worker_id == worker_id).first()
    if not worker:
        from fastapi import HTTPException
        raise HTTPException(404, "Worker not found")
    week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
    weekly = db.query(Claim).filter(
        Claim.worker_id == worker_id,
        Claim.created_at >= week_start,
        Claim.status == "success"
    ).all()
    total_payout = sum(c.amount for c in weekly)
    events_count = len(weekly)
    from backend.claims.payout_service import PLAN_WEEKLY_CAP
    cap = PLAN_WEEKLY_CAP.get(worker.plan, 500)
    estimated_loss = sum(
        worker.avg_daily_earnings * (c.overlap_hours / 8) for c in weekly
    )
    return {
        "worker_id": worker_id,
        "plan": worker.plan,
        "total_payout_this_week": round(total_payout, 2),
        "estimated_loss_without_insurance": round(estimated_loss, 2),
        "net_saving": round(total_payout, 2),
        "events_this_week": events_count,
        "weekly_cap_used": round(total_payout, 2),
        "weekly_cap_remaining": round(max(0, cap - total_payout), 2),
    }

@router.get("/{claim_id}")
def get_claim(claim_id: str, db: Session = Depends(get_db)):
    c = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not c:
        from fastapi import HTTPException
        raise HTTPException(404, "Claim not found")
    return _claim_dict(c)

def _run(worker_id, event_id):
    from database import SessionLocal
    from claims.payout_service import run_payout_pipeline
    db = SessionLocal()
    try:
        run_payout_pipeline(worker_id, event_id, db)
    finally:
        db.close()

def _claim_dict(c):
    return {
        "claim_id": c.claim_id, "worker_id": c.worker_id, "event_id": c.event_id,
        "amount": c.amount, "status": c.status,
        "overlap_hours": c.overlap_hours, "gps_confidence": c.gps_confidence,
        "anomaly_score": c.anomaly_score, "utr": c.utr,
        "created_at": c.created_at.isoformat(),
        "settled_at": c.settled_at.isoformat() if c.settled_at else None,
    }
