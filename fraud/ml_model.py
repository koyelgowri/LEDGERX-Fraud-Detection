import pickle
import numpy as np
import os
import logging
from sklearn.ensemble import IsolationForest
from datetime import datetime

logger = logging.getLogger(__name__)
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'fraud_model.pkl')
_model_cache = None

# Merchant risk mapping - you can load this from DB later
MERCHANT_RISK = {
    'amazon': 0.1,
    'flipkart': 0.1,
    'casino': 0.9,
    'crypto_exchange': 0.8,
    'darkweb': 1.0,
    'unknown': 0.3
}

def get_merchant_risk(merchant):
    """Return 0-1 risk score for merchant"""
    merchant = merchant.lower().strip()
    return MERCHANT_RISK.get(merchant, MERCHANT_RISK['unknown'])

def train_and_save_model():
    """Train model. In real life you'd use historical fraud data."""
    # Features: [amount, hour_of_day, velocity, merchant_risk]
    X_normal = np.array([
        [500, 14, 1, 0.1], [1200, 18, 2, 0.1], [50, 10, 1, 0.1], [2000, 15, 1, 0.1],
        [800, 12, 1, 0.1], [1500, 16, 2, 0.1], [300, 11, 1, 0.1], [2500, 19, 1, 0.1]
    ])
    # Fraud: huge amount, weird hour, high velocity, risky merchant
    X_fraud = np.array([
        [90000, 3, 8, 0.9], [120000, 2, 10, 0.8], [75000, 4, 6, 0.9],
        [95000, 1, 9, 0.9], [88000, 2, 7, 0.8], [99000, 3, 12, 0.9]
    ])
    
    X = np.vstack([X_normal, X_fraud])
    
    # contamination=0.4 because 6/14 = 42% fraud in training data
    model = IsolationForest(
        contamination=0.4, 
        random_state=42, 
        n_estimators=100,
        max_samples='auto'
    )
    model.fit(X)
    
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    logger.info(f"✅ Model saved to {MODEL_PATH}")
    return model

def load_model():
    global _model_cache
    if _model_cache is not None:
        return _model_cache
    
    if not os.path.exists(MODEL_PATH):
        logger.warning("Model not found. Training new model...")
        _model_cache = train_and_save_model()
    else:
        with open(MODEL_PATH, 'rb') as f:
            _model_cache = pickle.load(f)
        logger.info("Model loaded from disk")
    return _model_cache

def predict_fraud(amount, hour, velocity_count, merchant="unknown"):
    """
    Returns: is_fraud_bool, fraud_score_0_to_1, details_dict
    Consumer.py expects 3 return values.
    """
    try:
        model = load_model()
        
        # Feature engineering
        merchant_risk = get_merchant_risk(merchant)
        features = np.array([[float(amount), int(hour), int(velocity_count), merchant_risk]])
        
        # IsolationForest: -1 = anomaly/fraud, 1 = normal
        prediction = model.predict(features)[0]
        
        # decision_function: lower = more anomalous. Range roughly -0.5 to 0.5
        raw_score = model.decision_function(features)[0]
        
        # Convert to 0-1: invert so high = fraud, then sigmoid to smooth
        # Raw -0.2 -> ~0.85 fraud, Raw 0.2 -> ~0.15 fraud
        fraud_score = 1 / (1 + np.exp(raw_score * 10)) # *10 to sharpen
        fraud_score = np.clip(fraud_score, 0.0, 1.0)
        
        is_fraud = prediction == -1 or fraud_score > 0.7 # Hybrid threshold
        
        details = {
            "model": "IsolationForest_v1",
            "model_version": "2026.08.09",
            "features": {
                "amount": float(amount),
                "hour": int(hour),
                "velocity_count": int(velocity_count),
                "merchant": merchant,
                "merchant_risk": round(merchant_risk, 2)
            },
            "raw_score": round(float(raw_score), 4),
            "proba": round(float(fraud_score), 4),
            "threshold": 0.7,
            "prediction_label": "fraud" if is_fraud else "legit",
            "timestamp": datetime.now().isoformat()
        }
        
        return is_fraud, float(fraud_score), details
        
    except Exception as e:
        logger.error(f"ML prediction failed: {e}", exc_info=True)
        # Fail-safe: if ML breaks, don't block txn
        details = {
            "model": "IsolationForest_v1",
            "error": str(e),
            "prediction_label": "error",
            "proba": 0.0
        }
        return False, 0.0, details