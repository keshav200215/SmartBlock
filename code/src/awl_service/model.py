# src/awl_service/model.py
import os, joblib, pandas as pd, numpy as np
from dataclasses import dataclass
from sklearn.ensemble import IsolationForest

DEFAULT_FEATURES = [
    # common
    "moves","in_count","out_count","median_dt_sec","net_ratio",
    # btc
    "btc_in","btc_out","net_btc",
    # eth
    "native_in_sum","native_out_sum","native_net","token_moves","tokens_touched","approvals",
]

@dataclass
class Bundle:
    model: any
    features: list
    is_unsupervised: bool = True
    # Optional min/max for score normalization
    min_score: float = 0.0
    max_score: float = 1.0

def train_unsupervised(btc_csv: str, eth_csv: str, model_path: str) -> Bundle:
    btc = pd.read_csv(btc_csv)
    eth = pd.read_csv(eth_csv)

    # union columns (missing → 0)
    for c in DEFAULT_FEATURES:
        if c not in btc.columns: btc[c] = 0
        if c not in eth.columns: eth[c] = 0

    df = pd.concat([btc[DEFAULT_FEATURES], eth[DEFAULT_FEATURES]], ignore_index=True).fillna(0.0)
    X = df[DEFAULT_FEATURES].astype(float).values

    iso = IsolationForest(n_estimators=300, contamination=0.05, random_state=42)
    iso.fit(X)

    # calibration range for -score_samples
    raw = -iso.score_samples(X)
    min_s, max_s = float(raw.min()), float(raw.max())

    bundle = Bundle(model=iso, features=DEFAULT_FEATURES, is_unsupervised=True, min_score=min_s, max_score=max_s)
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(bundle, model_path)
    return bundle

def load_model(model_path: str) -> Bundle:
    return joblib.load(model_path)

def score_unsupervised(bundle: Bundle, feats: dict) -> float:
    x = np.array([[float(feats.get(f, 0.0)) for f in bundle.features]])
    raw = -bundle.model.score_samples(x)[0]
    # normalize 0..1 using train distribution range
    denom = (bundle.max_score - bundle.min_score) or 1.0
    return float((raw - bundle.min_score) / denom)
