"""
Isolation Forest anomaly detector for fraud detection.
Scores 0.0 (normal) → 1.0 (highly anomalous).
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib, os

MODEL_DIR  = os.path.dirname(__file__)
MODEL_PATH = os.path.join(MODEL_DIR, "fraud_model.pkl")
SCALER_PATH= os.path.join(MODEL_DIR, "scaler.pkl")

FEATURES = [
    "claims_last_4_weeks", "weeks_active", "zone_disruption_freq",
    "avg_daily_earnings", "avg_deliveries_per_day", "is_multi_platform",
]

def train():
    data_path = os.path.join(MODEL_DIR, "../data/training_data.csv")
    df = pd.read_csv(data_path)

    # Train only on non-fraud samples so fraud deviates from the norm
    normal = df[df["is_fraud"] == 0]
    X = normal[FEATURES].fillna(0)

    scaler = StandardScaler()
    X_sc = scaler.fit_transform(X)

    # contamination=0.03 → expects ~3% anomalies in production
    model = IsolationForest(
        n_estimators=200, contamination=0.03,
        random_state=42, n_jobs=-1
    )
    model.fit(X_sc)

    # Validate — fraud cases should score higher
    X_all = scaler.transform(df[FEATURES].fillna(0))
    raw_scores = model.decision_function(X_all)
    # Convert: lower decision_function = more anomalous → invert and normalise to [0,1]
    normalised = 1 - (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min())
    fraud_avg  = normalised[df["is_fraud"] == 1].mean()
    normal_avg = normalised[df["is_fraud"] == 0].mean()
    print(f"✅ Fraud model trained")
    print(f"   Fraud avg score: {fraud_avg:.3f} | Normal avg: {normal_avg:.3f}")

    joblib.dump(model,  MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    return model, scaler


def get_anomaly_score(worker) -> float:
    """
    Takes a Worker ORM object (or dict with same keys).
    Returns anomaly score 0.0–1.0.
    """
    if not os.path.exists(MODEL_PATH):
        return _rule_based_score(worker)

    model  = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)

    def _get(obj, key, default=0):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    row = [[
        _get(worker, "claims_last_4_weeks"),
        _get(worker, "weeks_active"),
        _get(worker, "zone_disruption_freq", 0.3),
        _get(worker, "avg_daily_earnings", 500),
        _get(worker, "avg_deliveries_per_day", 20),
        _get(worker, "is_multi_platform", 0),
    ]]
    X = np.array(row, dtype=float)
    X_sc = scaler.transform(X)
    raw = model.decision_function(X_sc)[0]

    # Normalise to [0, 1] using observed range from training
    # Approximate inversion: raw typically ranges from -0.5 to 0.5
    score = float(np.clip(0.5 - raw, 0, 1))
    return round(score, 4)


def _rule_based_score(worker) -> float:
    """Fallback if model not trained — used in Phase 1."""
    def _get(obj, key, default=0):
        if isinstance(obj, dict): return obj.get(key, default)
        return getattr(obj, key, default)
    score = 0.0
    claims = _get(worker, "claims_last_4_weeks")
    weeks  = _get(worker, "weeks_active")
    if claims >= 4: score += 0.3
    if claims >= 6: score += 0.3
    if weeks < 2:   score += 0.2
    return min(score, 1.0)


# Anti-spoofing checks
def check_gps_spoofing(gps_pings: list) -> dict:
    """
    Detect GPS spoofing signatures from a list of ping dicts.
    Returns a spoofing assessment.
    """
    if len(gps_pings) < 3:
        return {"spoofing_detected": False, "reason": "insufficient_data", "confidence": 0.0}

    signals = []
    # Signal 1: Suspiciously perfect accuracy
    accuracies = [p.get("accuracy_m", 10) for p in gps_pings]
    avg_acc = np.mean(accuracies)
    acc_std = np.std(accuracies)
    if avg_acc < 4.0 and acc_std < 0.5:
        signals.append({"signal": "perfect_accuracy", "detail": f"Avg accuracy {avg_acc:.1f}m, std {acc_std:.2f}m"})

    # Signal 2: Impossible movement speed between pings
    for i in range(1, len(gps_pings)):
        p1, p2 = gps_pings[i-1], gps_pings[i]
        if "lat" in p1 and "lat" in p2:
            from math import radians, sin, cos, sqrt, atan2
            R = 6371
            dlat = radians(p2["lat"] - p1["lat"])
            dlon = radians(p2["lon"] - p1["lon"])
            a = sin(dlat/2)**2 + cos(radians(p1["lat"]))*cos(radians(p2["lat"]))*sin(dlon/2)**2
            dist_km = R * 2 * atan2(sqrt(a), sqrt(1-a))
            if dist_km > 3.0:  # >3 km jump between 10-min pings = >18 kph = suspicious
                signals.append({"signal": "location_teleport",
                               "detail": f"{dist_km:.1f}km jump between consecutive pings"})

    # Signal 3: Uniform timestamp intervals (spoofing apps ping at exact intervals)
    if len(gps_pings) >= 5 and all("timestamp" in p for p in gps_pings):
        try:
            from datetime import datetime
            times = [datetime.fromisoformat(p["timestamp"]) for p in gps_pings]
            gaps = [(times[i] - times[i-1]).seconds for i in range(1, len(times))]
            if gaps and np.std(gaps) < 2:
                signals.append({"signal": "uniform_timing",
                               "detail": f"Ping intervals uniform: std={np.std(gaps):.1f}s"})
        except Exception:
            pass

    spoofing_score = min(len(signals) * 0.35, 1.0)
    return {
        "spoofing_detected": spoofing_score >= 0.6,
        "spoofing_score": round(spoofing_score, 2),
        "signals_found": signals,
        "confidence": round(spoofing_score, 2),
    }


if __name__ == "__main__":
    train()
