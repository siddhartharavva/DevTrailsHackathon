"""
Generate synthetic training data for all three ML models.
Run: python generate_data.py
"""
import pandas as pd
import numpy as np
import os

np.random.seed(42)
N = 3000
DATA_DIR = os.path.dirname(__file__)

CITIES   = ["bengaluru", "mumbai", "delhi", "hyderabad", "chennai", "kolkata", "pune"]
SEGMENTS = ["grocery", "food", "ecommerce"]
SEASONS  = ["monsoon", "summer", "winter", "spring"]
SHIFTS   = ["day", "night"]

CITY_RISK = {"bengaluru":1.00,"mumbai":1.40,"delhi":1.28,"hyderabad":1.10,
             "chennai":1.22,"kolkata":1.32,"pune":0.95}

def generate():
    city    = np.random.choice(CITIES, N)
    segment = np.random.choice(SEGMENTS, N, p=[0.5, 0.35, 0.15])
    season  = np.random.choice(SEASONS,  N, p=[0.35, 0.25, 0.20, 0.20])
    shift   = np.random.choice(SHIFTS,   N, p=[0.72, 0.28])

    earnings = np.random.normal(520, 120, N).clip(200, 1000)
    deliveries = np.where(segment == "grocery",
                    np.random.randint(18, 30, N),
                    np.where(segment == "food",
                        np.random.randint(6, 16, N),
                        np.random.randint(8, 20, N)))
    distance = np.where(segment == "grocery",
                    np.random.uniform(0.8, 2.5, N),
                    np.where(segment == "food",
                        np.random.uniform(2.0, 6.0, N),
                        np.random.uniform(3.0, 10.0, N)))

    weeks_active = np.random.randint(0, 104, N)
    claims_4wk   = np.random.poisson(0.7, N).clip(0, 8)
    zone_freq    = np.array([CITY_RISK[c] * np.random.uniform(0.7, 1.3) for c in city]).clip(0.5, 1.8)
    is_multi     = np.random.choice([0, 1], N, p=[0.65, 0.35])

    # ── Risk multiplier target ──────────────────────────────────────────────
    risk_mult = (
        1.0
        + (zone_freq - 0.9) * 0.4
        + (claims_4wk / 8)  * 0.35
        + (shift == "night").astype(int) * 0.12
        + (season == "monsoon").astype(int) * 0.18
        - (weeks_active / 104) * 0.12
        + np.random.normal(0, 0.04, N)
    ).clip(0.7, 1.5)

    # ── Compensation amount target ──────────────────────────────────────────
    overlap_hours = np.random.uniform(1, 10, N)
    disruption_speed = np.where(segment=="grocery", 0.70,
                         np.where(segment=="food", 1.0, 0.55))
    shift_hours = np.where(shift=="day", 12, 10)
    hourly = (earnings / shift_hours) * disruption_speed
    raw_loss = hourly * overlap_hours
    replacement = np.where(earnings < 350, 0.40,
                    np.where(earnings < 600, 0.60, 0.80))
    severity_factor = np.random.choice([0.50, 0.75, 1.0], N, p=[0.2, 0.4, 0.4])
    compensation = (raw_loss * replacement * severity_factor * np.random.uniform(0.85, 1.05, N)).clip(0, 900)

    # ── Anomaly score target ────────────────────────────────────────────────
    anomaly = np.zeros(N)
    anomaly += (claims_4wk >= 4).astype(float) * 0.3
    anomaly += (claims_4wk >= 6).astype(float) * 0.3
    anomaly += (weeks_active < 2).astype(float) * 0.2
    anomaly += np.random.uniform(0, 0.15, N)
    anomaly = anomaly.clip(0, 1.0)
    # Force ~3% fraud cases
    fraud_idx = np.random.choice(N, int(N * 0.03), replace=False)
    anomaly[fraud_idx] = np.random.uniform(0.65, 0.95, len(fraud_idx))
    is_fraud = (anomaly >= 0.6).astype(int)

    df = pd.DataFrame({
        "city": city, "segment": segment, "season": season, "shift": shift,
        "avg_daily_earnings": earnings.round(2),
        "avg_deliveries_per_day": deliveries,
        "avg_delivery_distance": distance.round(2),
        "weeks_active": weeks_active,
        "claims_last_4_weeks": claims_4wk,
        "zone_disruption_freq": zone_freq.round(3),
        "is_multi_platform": is_multi,
        "overlap_hours": overlap_hours.round(2),
        "severity_factor": severity_factor,
        "risk_multiplier": risk_mult.round(4),
        "compensation_amount": compensation.round(2),
        "anomaly_score": anomaly.round(4),
        "is_fraud": is_fraud,
    })

    out = os.path.join(DATA_DIR, "training_data.csv")
    df.to_csv(out, index=False)
    print(f"✅ Generated {N} samples → {out}")
    print(f"   Fraud rate: {is_fraud.mean()*100:.1f}%")
    print(f"   Avg risk multiplier: {risk_mult.mean():.3f}")
    print(f"   Avg compensation: ₹{compensation.mean():.0f}")
    return df

if __name__ == "__main__":
    generate()
