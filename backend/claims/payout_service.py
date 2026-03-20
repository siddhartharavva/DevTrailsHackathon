import uuid, time, os, requests
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import Worker, DisruptionEvent, Claim, PayoutAttempt, Policy

# ── CONFIG ───────────────────────────────────────────────────────────────────

PLAN_WEEKLY_CAP = {"basic": 250, "standard": 500, "max": 900}
INCOME_REPLACEMENT = {"basic": 0.40, "standard": 0.60, "max": 0.80}
SEGMENT_DISRUPTION_SPEED = {"grocery": 0.70, "food": 1.0, "ecommerce": 0.55}
MAX_RETRIES = 3
RETRY_DELAYS = [10, 30, 60]   # seconds (short for demo)

RAZORPAY_KEY    = os.getenv("RAZORPAY_KEY_ID", "rzp_test_demo")
RAZORPAY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "demo_secret")
RAZORPAY_ACCOUNT= os.getenv("RAZORPAY_ACCOUNT_NUMBER", "DEMO_ACCOUNT")
TWILIO_SID      = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM     = os.getenv("TWILIO_PHONE", "")
DEMO_MODE       = os.getenv("DEMO_MODE", "true").lower() == "true"

# ── MAIN ORCHESTRATOR ────────────────────────────────────────────────────────

def run_payout_pipeline(worker_id: str, event_id: str, db: Session) -> dict:
    """
    Full pipeline: eligibility → amount → transfer → notify.
    Idempotent — safe to call multiple times.
    """
    # Idempotency guard
    idem_key = f"shieldshift_{worker_id}_{event_id}"
    existing = db.query(Claim).filter(Claim.idempotency_key == idem_key).first()
    if existing:
        return {"skipped": True, "reason": "already_processed", "claim_id": existing.claim_id,
                "status": existing.status}

    worker = db.query(Worker).filter(Worker.worker_id == worker_id).first()
    event  = db.query(DisruptionEvent).filter(DisruptionEvent.event_id == event_id).first()
    if not worker or not event:
        return {"skipped": True, "reason": "worker_or_event_not_found"}

    # 1. Eligibility
    from trigger_engine.routes import run_full_eligibility
    eligibility = run_full_eligibility(worker, event, db)
    if not eligibility["eligible"]:
        return {"skipped": True, "reason": eligibility.get("rejection_reason"), "eligibility": eligibility}

    # 2. Run anomaly detection
    anomaly_score = _anomaly_check(worker, db)
    if anomaly_score >= 0.6:
        _write_claim(db, worker_id, event_id, 0, "rejected", idem_key, eligibility,
                     anomaly_score=anomaly_score, failure_reason="anomaly_detected")
        return {"skipped": True, "reason": "anomaly_score_too_high", "score": anomaly_score}

    # 3. Calculate amount
    payout = _calculate_payout(worker, event, eligibility, db)
    if payout["final_payout"] <= 0:
        return {"skipped": True, "reason": "weekly_cap_exhausted"}

    # 4. Write pending claim
    claim_id = f"CLM_{uuid.uuid4().hex[:10].upper()}"
    claim = _write_claim(db, worker_id, event_id, payout["final_payout"], "pending",
                         idem_key, eligibility, claim_id=claim_id, anomaly_score=anomaly_score)

    # 5. Execute payout with retry
    result = _execute_with_retry(payout, worker.upi_id, claim_id, db)

    if result["success"]:
        db.query(Claim).filter(Claim.claim_id == claim_id).update({
            "status": "success",
            "razorpay_payout_id": result.get("razorpay_payout_id"),
            "utr": result.get("utr"),
            "settled_at": datetime.utcnow(),
            "attempt_count": result.get("attempts")
        })
        db.commit()
        _notify_worker(worker, payout["final_payout"], event, result.get("utr", ""))
        # Update worker stats
        db.query(Worker).filter(Worker.worker_id == worker_id).update({
            "claims_last_4_weeks": worker.claims_last_4_weeks + 1
        })
        db.commit()
    else:
        db.query(Claim).filter(Claim.claim_id == claim_id).update({
            "status": "manual_review",
            "failure_reason": "max_retries_exceeded"
        })
        db.commit()
        _notify_worker_processing(worker, payout["final_payout"], event)

    return {
        "claim_id": claim_id,
        "worker_id": worker_id,
        "event_id": event_id,
        "amount": payout["final_payout"],
        "status": "success" if result["success"] else "manual_review",
        "payout_breakdown": payout,
        "anomaly_score": anomaly_score,
        "eligibility": eligibility,
    }


# ── PAYOUT CALCULATION ───────────────────────────────────────────────────────

def _calculate_payout(worker, event, eligibility, db) -> dict:
    overlap_hours = eligibility["shift_check"]["overlap_hours"]
    shift_hours   = worker.shift_end_hour - worker.shift_start_hour
    daily         = worker.avg_daily_earnings
    deliveries    = max(worker.avg_deliveries_per_day, 1)

    deliveries_per_hour = deliveries / shift_hours
    earnings_per_del    = daily / deliveries
    base_hourly         = deliveries_per_hour * earnings_per_del
    disruption_speed    = SEGMENT_DISRUPTION_SPEED.get(worker.platform_segment, 1.0)
    effective_hourly    = base_hourly * disruption_speed

    raw_loss   = effective_hourly * overlap_hours
    raw_payout = raw_loss * INCOME_REPLACEMENT[worker.plan]
    confidence = eligibility["zone_check"].get("payout_factor", 1.0)
    adjusted   = raw_payout * confidence

    # Weekly cap
    week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
    paid_this_week = db.query(Claim).filter(
        Claim.worker_id == worker.worker_id,
        Claim.created_at >= week_start,
        Claim.status == "success"
    ).with_entities(Claim.amount).all()
    already_paid = sum(r[0] for r in paid_this_week)
    cap_remaining = max(0, PLAN_WEEKLY_CAP[worker.plan] - already_paid)
    final = min(round(adjusted, 2), cap_remaining)

    return {
        "deliveries_per_hour": round(deliveries_per_hour, 2),
        "earnings_per_delivery": round(earnings_per_del, 2),
        "effective_hourly_loss": round(effective_hourly, 2),
        "disruption_hours": overlap_hours,
        "raw_loss": round(raw_loss, 2),
        "income_replacement_pct": INCOME_REPLACEMENT[worker.plan],
        "raw_payout": round(raw_payout, 2),
        "confidence_factor": confidence,
        "adjusted_payout": round(adjusted, 2),
        "already_paid_this_week": already_paid,
        "cap_remaining": cap_remaining,
        "final_payout": final,
        "capped": final < round(adjusted, 2),
    }


# ── PAYMENT EXECUTION ────────────────────────────────────────────────────────

def _execute_with_retry(payout_calc, upi_id, claim_id, db):
    for attempt in range(MAX_RETRIES):
        result = _execute_upi_payout(payout_calc, upi_id)
        if result["success"]:
            result["attempts"] = attempt + 1
            return result
        db.add(PayoutAttempt(
            claim_id=claim_id, attempt=attempt+1,
            error_code=result.get("error_code"), error_msg=result.get("error")
        ))
        db.commit()
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAYS[attempt])
    return {"success": False}


def _execute_upi_payout(payout_calc, upi_id) -> dict:
    """
    In DEMO_MODE: simulate a successful Razorpay response.
    In production: call Razorpay Payouts API.
    """
    if DEMO_MODE:
        import random
        fake_utr = f"UTR{datetime.utcnow().strftime('%Y%m%d')}{random.randint(10000,99999)}"
        return {
            "success": True,
            "razorpay_payout_id": f"pout_{uuid.uuid4().hex[:16]}",
            "status": "processed",
            "amount_inr": payout_calc["final_payout"],
            "utr": fake_utr,
            "mode": "DEMO"
        }

    idem_key = f"shieldshift_{uuid.uuid4().hex[:8]}"
    payload = {
        "account_number": RAZORPAY_ACCOUNT,
        "amount": int(payout_calc["final_payout"] * 100),
        "currency": "INR",
        "mode": "UPI",
        "purpose": "payout",
        "fund_account": {
            "account_type": "vpa",
            "vpa": {"address": upi_id},
            "contact": {"name": "ShieldShift Partner", "type": "employee",
                        "reference_id": str(uuid.uuid4())}
        },
        "queue_if_low_balance": True,
        "reference_id": idem_key,
        "narration": "ShieldShift income protection payout",
    }
    try:
        r = requests.post(
            "https://api.razorpay.com/v1/payouts",
            json=payload, auth=(RAZORPAY_KEY, RAZORPAY_SECRET),
            headers={"X-Payout-Idempotency": idem_key}, timeout=10
        )
        data = r.json()
        if r.status_code == 200 and data.get("status") in ("processing", "processed"):
            return {"success": True, "razorpay_payout_id": data["id"],
                    "status": data["status"], "amount_inr": payout_calc["final_payout"],
                    "utr": data.get("utr")}
        return {"success": False, "error": data.get("error", {}).get("description"),
                "error_code": data.get("error", {}).get("code")}
    except Exception as e:
        return {"success": False, "error": str(e), "error_code": "network_error"}


# ── NOTIFICATIONS ────────────────────────────────────────────────────────────

def _notify_worker(worker, amount, event, utr):
    msg = f"ShieldShift: Rs.{amount:.0f} credited to your UPI for {event.description[:40]}. Ref: {utr}"
    print(f"[SMS] → +91{worker.phone}: {msg}")
    if not DEMO_MODE and TWILIO_SID:
        try:
            from twilio.rest import Client
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            client.messages.create(body=msg, from_=TWILIO_FROM, to=f"+91{worker.phone}")
        except Exception as e:
            print(f"SMS failed: {e}")


def _notify_worker_processing(worker, amount, event):
    print(f"[SMS] → +91{worker.phone}: ShieldShift: Rs.{amount:.0f} claim under review. We'll resolve in 24h.")


# ── ANOMALY DETECTION ────────────────────────────────────────────────────────

def _anomaly_check(worker, db) -> float:
    """
    Rule-based anomaly score (0.0–1.0).
    Replaced by Isolation Forest in Phase 2.
    """
    score = 0.0
    if worker.claims_last_4_weeks >= 4:
        score += 0.3
    if worker.claims_last_4_weeks >= 6:
        score += 0.3
    if worker.weeks_active < 2:
        score += 0.2
    try:
        from ml.fraud_detection.predict import get_anomaly_score
        score = get_anomaly_score(worker)
    except Exception:
        pass
    return min(score, 1.0)


# ── DB HELPERS ───────────────────────────────────────────────────────────────

def _write_claim(db, worker_id, event_id, amount, status, idem_key, eligibility,
                 claim_id=None, anomaly_score=0.0, failure_reason=None):
    claim = Claim(
        claim_id=claim_id or f"CLM_{uuid.uuid4().hex[:10].upper()}",
        worker_id=worker_id, event_id=event_id, amount=amount, status=status,
        payout_factor=eligibility.get("payout_factor", 0),
        overlap_hours=eligibility.get("shift_check", {}).get("overlap_hours", 0),
        gps_confidence=eligibility.get("zone_check", {}).get("confidence", 0),
        anomaly_score=anomaly_score, idempotency_key=idem_key,
        failure_reason=failure_reason, eligibility_detail=eligibility
    )
    db.add(claim)
    db.commit()
    return claim
