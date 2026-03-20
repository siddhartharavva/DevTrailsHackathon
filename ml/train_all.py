"""
Train all three ML models in sequence.
Run from /ml directory: python train_all.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 50)
print("ShieldShift — ML Training Pipeline")
print("=" * 50)

print("\n[1/4] Generating synthetic training data...")
from data.generate_data import generate
df = generate()

print("\n[2/4] Training risk model (XGBoost Regressor)...")
from risk_model.train import train as train_risk
train_risk()

print("\n[3/4] Training payout compensation model (XGBoost Regressor)...")
from payout_model.train import train as train_payout
train_payout()

print("\n[4/4] Training fraud detection model (Isolation Forest)...")
from fraud_detection.train import train as train_fraud
train_fraud()

print("\n" + "=" * 50)
print("✅ All models trained successfully.")
print("   Models saved to their respective directories.")
print("=" * 50)
