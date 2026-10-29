from functools import lru_cache
from pathlib import Path
import json, joblib
import pandas as pd
from fastapi import HTTPException

ROOT=Path(__file__).resolve().parents[3]
ARTIFACT=ROOT/'ml'/'artifacts'/'fraud_model.joblib'
META=ROOT/'ml'/'artifacts'/'metadata.json'
FEATURES=['distance_from_home','distance_from_last_transaction','ratio_to_median_purchase_price','repeat_retailer','used_chip','used_pin_number','online_order']

@lru_cache(maxsize=1)
def load_model():
    if not ARTIFACT.exists() or not META.exists():
        raise HTTPException(503,'Model not trained. Run: python ml/train.py')
    model, meta = joblib.load(ARTIFACT), json.loads(META.read_text())
    if meta.get('features') != FEATURES or list(model.feature_names_in_) != FEATURES:
        raise HTTPException(503, 'Model feature order mismatch. Retrain with python ml/train.py')
    return model, meta

def result_for(features, probability, meta):
    threshold = float(meta.get('threshold', 0.5))
    risk = 'high' if probability >= threshold else ('medium' if probability >= threshold * .5 else 'low')
    signals = []
    if features['distance_from_home'] > 100: signals.append('Far from usual home location')
    if features['distance_from_last_transaction'] > 100: signals.append('Far from previous transaction')
    if features['ratio_to_median_purchase_price'] > 3: signals.append('Larger than typical purchase')
    if features['online_order'] and not features['used_chip']: signals.append('Online transaction without chip')
    return {'fraud_probability': round(float(probability), 4),
            'predicted_fraud': bool(probability >= threshold), 'risk_level': risk,
            'model_version': meta['version'], 'explanation': signals}

def predict_many(records):
    if not records: return []
    model, meta = load_model()
    X = pd.DataFrame(records)[FEATURES].astype(float)
    probabilities = model.predict_proba(X)[:, 1]
    return [result_for(row, p, meta) for row, p in zip(records, probabilities)]

def predict(payload):
    return predict_many([{key: float(getattr(payload, key)) for key in FEATURES}])[0]
