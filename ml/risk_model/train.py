"""
XGBoost Regressor — predicts risk multiplier (0.7–1.5) per worker.
Train: python train.py
"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error
import xgboost as xgb
import joblib, os

MODEL_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(MODEL_DIR, "../data/training_data.csv")
MODEL_PATH = os.path.join(MODEL_DIR, "risk_model.pkl")
ENC_PATH   = os.path.join(MODEL_DIR, "encoders.pkl")

FEATURES = [
    "city_enc", "segment_enc", "season_enc", "shift_enc",
    "avg_daily_earnings", "avg_deliveries_per_day",
    "avg_delivery_distance", "weeks_active",
    "claims_last_4_weeks", "zone_disruption_freq", "is_multi_platform"
]

def train():
    df = pd.read_csv(DATA_PATH)
    enc = {
        "city":    LabelEncoder().fit(df["city"]),
        "segment": LabelEncoder().fit(df["segment"]),
        "season":  LabelEncoder().fit(df["season"]),
        "shift":   LabelEncoder().fit(df["shift"]),
    }
    df["city_enc"]    = enc["city"].transform(df["city"])
    df["segment_enc"] = enc["segment"].transform(df["segment"])
    df["season_enc"]  = enc["season"].transform(df["season"])
    df["shift_enc"]   = enc["shift"].transform(df["shift"])

    X = df[FEATURES]
    y = df["risk_multiplier"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBRegressor(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=0
    )
    model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=False)
    mae = mean_absolute_error(y_te, model.predict(X_te))
    print(f"✅ Risk model trained — MAE: {mae:.4f}")

    joblib.dump(model, MODEL_PATH)
    joblib.dump(enc, ENC_PATH)
    print(f"   Saved → {MODEL_PATH}")
    return model, enc


def get_risk_multiplier(worker_profile: dict) -> float:
    """
    worker_profile keys:
      city, segment, season, shift, avg_daily_earnings,
      avg_deliveries_per_day, avg_delivery_distance,
      weeks_active, claims_last_4_weeks,
      zone_disruption_freq, is_multi_platform
    """
    # Fall back to rule-based if model not trained yet
    if not os.path.exists(MODEL_PATH):
        return _rule_based(worker_profile)

    model = joblib.load(MODEL_PATH)
    enc   = joblib.load(ENC_PATH)

    def safe_encode(encoder, val, default=0):
        try:
            return encoder.transform([val])[0]
        except ValueError:
            return default

    row = {
        "city_enc":              safe_encode(enc["city"],    worker_profile.get("city", "bengaluru")),
        "segment_enc":           safe_encode(enc["segment"], worker_profile.get("segment", "grocery")),
        "season_enc":            safe_encode(enc["season"],  worker_profile.get("season", "summer")),
        "shift_enc":             safe_encode(enc["shift"],   worker_profile.get("shift", "day")),
        "avg_daily_earnings":    worker_profile.get("avg_daily_earnings", 500),
        "avg_deliveries_per_day":worker_profile.get("avg_deliveries_per_day", 20),
        "avg_delivery_distance": worker_profile.get("avg_delivery_distance", 2.0),
        "weeks_active":          worker_profile.get("weeks_active", 0),
        "claims_last_4_weeks":   worker_profile.get("claims_last_4_weeks", 0),
        "zone_disruption_freq":  worker_profile.get("zone_disruption_freq", 0.3),
        "is_multi_platform":     worker_profile.get("is_multi_platform", 0),
    }
    X = pd.DataFrame([row])
    mult = float(model.predict(X)[0])
    return float(np.clip(mult, 0.7, 1.5))


def _rule_based(p: dict) -> float:
    """Transparent rule-based fallback used in Phase 1 before enough data to train."""
    CITY_RISK = {"bengaluru":1.00,"mumbai":1.40,"delhi":1.28,"hyderabad":1.10,
                 "chennai":1.22,"kolkata":1.32,"pune":0.95}
    base = 1.0
    base += (CITY_RISK.get(p.get("city","bengaluru"), 1.0) - 1.0) * 0.3
    base += 0.12 if p.get("shift") == "night" else 0
    base += 0.18 if p.get("season") == "monsoon" else 0
    base += min(p.get("claims_last_4_weeks", 0) / 8, 1.0) * 0.35
    base -= min(p.get("weeks_active", 0) / 104, 1.0) * 0.12
    return float(np.clip(base, 0.7, 1.5))


if __name__ == "__main__":
    train()
