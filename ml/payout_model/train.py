"""
XGBoost Regressor — predicts compensation amount in ₹ given event + worker context.
"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error
import xgboost as xgb
import joblib, os

MODEL_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(MODEL_DIR, "payout_model.pkl")
ENC_PATH   = os.path.join(MODEL_DIR, "encoders.pkl")

FEATURES = [
    "segment_enc", "city_enc", "season_enc",
    "avg_daily_earnings", "avg_deliveries_per_day",
    "overlap_hours", "severity_factor",
    "zone_disruption_freq", "gps_confidence",
]

def train():
    data_path = os.path.join(MODEL_DIR, "../data/training_data.csv")
    df = pd.read_csv(data_path)
    df["gps_confidence"] = np.random.uniform(0.6, 1.0, len(df))

    enc = {
        "segment": LabelEncoder().fit(df["segment"]),
        "city":    LabelEncoder().fit(df["city"]),
        "season":  LabelEncoder().fit(df["season"]),
    }
    df["segment_enc"] = enc["segment"].transform(df["segment"])
    df["city_enc"]    = enc["city"].transform(df["city"])
    df["season_enc"]  = enc["season"].transform(df["season"])

    X = df[FEATURES]
    y = df["compensation_amount"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBRegressor(
        n_estimators=300, max_depth=5, learning_rate=0.04,
        subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=0
    )
    model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=False)
    mae = mean_absolute_error(y_te, model.predict(X_te))
    print(f"✅ Payout model trained — MAE: ₹{mae:.2f}")

    joblib.dump(model, MODEL_PATH)
    joblib.dump(enc, ENC_PATH)
    return model, enc


def predict_compensation(features: dict) -> float:
    """
    features: segment, city, season, avg_daily_earnings,
              avg_deliveries_per_day, overlap_hours,
              severity_factor, zone_disruption_freq, gps_confidence
    """
    if not os.path.exists(MODEL_PATH):
        return _formula_fallback(features)

    model = joblib.load(MODEL_PATH)
    enc   = joblib.load(ENC_PATH)

    def safe_enc(e, v, d=0):
        try: return e.transform([v])[0]
        except ValueError: return d

    row = {
        "segment_enc":          safe_enc(enc["segment"], features.get("segment","grocery")),
        "city_enc":             safe_enc(enc["city"],    features.get("city","bengaluru")),
        "season_enc":           safe_enc(enc["season"],  features.get("season","summer")),
        "avg_daily_earnings":   features.get("avg_daily_earnings", 500),
        "avg_deliveries_per_day":features.get("avg_deliveries_per_day", 20),
        "overlap_hours":        features.get("overlap_hours", 4),
        "severity_factor":      features.get("severity_factor", 0.75),
        "zone_disruption_freq": features.get("zone_disruption_freq", 0.3),
        "gps_confidence":       features.get("gps_confidence", 1.0),
    }
    X = pd.DataFrame([row])
    return float(np.clip(model.predict(X)[0], 0, 900))


def _formula_fallback(f: dict) -> float:
    """Phase 1 transparent formula — explainable without trained model."""
    SPEED = {"grocery": 0.70, "food": 1.0, "ecommerce": 0.55}
    REPLACE = {"grocery": 0.60, "food": 0.60, "ecommerce": 0.60}
    shift_hours = 12
    hourly = (f.get("avg_daily_earnings", 500) / shift_hours) * SPEED.get(f.get("segment","food"), 1.0)
    raw = hourly * f.get("overlap_hours", 4)
    payout = raw * REPLACE.get(f.get("segment","food"), 0.60)
    payout *= f.get("severity_factor", 0.75)
    payout *= f.get("gps_confidence", 1.0)
    return round(float(np.clip(payout, 0, 900)), 2)


if __name__ == "__main__":
    train()
