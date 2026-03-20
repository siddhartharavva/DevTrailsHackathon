from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shieldshift_dev.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ── MODELS ──────────────────────────────────────────────────────────────────

class Worker(Base):
    __tablename__ = "workers"
    worker_id             = Column(String, primary_key=True, index=True)
    phone                 = Column(String, unique=True, index=True)
    name                  = Column(String, default="")
    city                  = Column(String)
    zone_id               = Column(String)
    zone_lat              = Column(Float)
    zone_lon              = Column(Float)
    platform              = Column(String)          # blinkit / zepto / swiggy
    platform_segment      = Column(String)          # grocery / food / ecommerce
    plan                  = Column(String)          # basic / standard / max
    upi_id                = Column(String)
    fcm_token             = Column(String, nullable=True)
    avg_daily_earnings    = Column(Float)
    avg_deliveries_per_day= Column(Integer)
    avg_delivery_distance = Column(Float)
    shift_start_hour      = Column(Integer, default=9)
    shift_end_hour        = Column(Integer, default=21)
    working_days          = Column(String, default="0,1,2,3,4,5,6")  # CSV of weekday ints
    weeks_active          = Column(Integer, default=0)
    claims_last_4_weeks   = Column(Integer, default=0)
    reliability_score     = Column(Float, default=0.5)
    language              = Column(String, default="en")
    policy_active         = Column(Boolean, default=True)
    created_at            = Column(DateTime, default=datetime.utcnow)
    last_active           = Column(DateTime, default=datetime.utcnow)

class Policy(Base):
    __tablename__ = "policies"
    policy_id             = Column(String, primary_key=True)
    worker_id             = Column(String, index=True)
    plan                  = Column(String)
    weekly_premium        = Column(Float)
    risk_multiplier       = Column(Float, default=1.0)
    income_replacement_pct= Column(Float)
    weekly_cap            = Column(Float)
    valid_from            = Column(DateTime)
    valid_until           = Column(DateTime)
    active                = Column(Boolean, default=True)
    created_at            = Column(DateTime, default=datetime.utcnow)

class GPSPing(Base):
    __tablename__ = "gps_pings"
    id                    = Column(Integer, primary_key=True, autoincrement=True)
    worker_id             = Column(String, index=True)
    lat                   = Column(Float)
    lon                   = Column(Float)
    accuracy_m            = Column(Float)
    battery_pct           = Column(Integer)
    app_state             = Column(String)
    timestamp             = Column(DateTime, default=datetime.utcnow, index=True)

class DisruptionEvent(Base):
    __tablename__ = "disruption_events"
    event_id              = Column(String, primary_key=True)
    trigger_type          = Column(String)          # RAIN_HEAVY / AQI_SEVERE / CIVIC_CURFEW etc.
    severity              = Column(String)          # red / orange / yellow
    zone_id               = Column(String, index=True)
    zone_center_lat       = Column(Float)
    zone_center_lon       = Column(Float)
    city                  = Column(String)
    description           = Column(String)
    raw_value             = Column(Float)           # mm/hr rain, AQI, etc.
    start_time            = Column(DateTime)
    end_time              = Column(DateTime, nullable=True)
    active                = Column(Boolean, default=True)
    source                = Column(String)          # open_meteo / cpcb / mock_curfew
    created_at            = Column(DateTime, default=datetime.utcnow)

class Claim(Base):
    __tablename__ = "claims"
    claim_id              = Column(String, primary_key=True)
    worker_id             = Column(String, index=True)
    event_id              = Column(String, index=True)
    amount                = Column(Float)
    status                = Column(String, default="pending")  # pending/success/failed/manual_review/rejected
    payout_factor         = Column(Float)
    overlap_hours         = Column(Float)
    gps_confidence        = Column(Float)
    anomaly_score         = Column(Float, default=0.0)
    razorpay_payout_id    = Column(String, nullable=True)
    utr                   = Column(String, nullable=True)
    idempotency_key       = Column(String, unique=True)
    failure_reason        = Column(String, nullable=True)
    attempt_count         = Column(Integer, default=0)
    created_at            = Column(DateTime, default=datetime.utcnow, index=True)
    settled_at            = Column(DateTime, nullable=True)
    eligibility_detail    = Column(JSON, nullable=True)

class PayoutAttempt(Base):
    __tablename__ = "payout_attempts"
    id                    = Column(Integer, primary_key=True, autoincrement=True)
    claim_id              = Column(String, index=True)
    attempt               = Column(Integer)
    error_code            = Column(String, nullable=True)
    error_msg             = Column(String, nullable=True)
    attempted_at          = Column(DateTime, default=datetime.utcnow)

# ── DB HELPERS ───────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialised")
