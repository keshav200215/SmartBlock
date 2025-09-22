# src/awl_service/app.py
import os
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from .schemas import ScoreRequest, ScoreResponse
from .features import compute_btc_features, compute_eth_features
from .model import train_unsupervised, load_model, score_unsupervised

load_dotenv()

BTC_CSV = os.getenv("BTC_FEATURES_CSV", "btc_wallet_features.csv")
ETH_CSV = os.getenv("ETH_FEATURES_CSV", "eth_wallet_features.csv")
MODEL_PATH = os.getenv("MODEL_PATH", "models/awl_model.joblib")
FLAG_THRESHOLD = int(os.getenv("FLAG_THRESHOLD", "7"))

app = FastAPI(title="AWL Service", version="1.0.0")

# lazy-load / train-on-start if missing
_bundle = None
def ensure_model():
    global _bundle
    if _bundle is not None: return _bundle
    if os.path.exists(MODEL_PATH):
        _bundle = load_model(MODEL_PATH)
    else:
        _bundle = train_unsupervised(BTC_CSV, ETH_CSV, MODEL_PATH)
    return _bundle

def rule_score(feats: dict) -> float:
    s = 0.0
    # high net outflow patterns
    if feats.get("net_ratio", 0) > 0.9 and (feats.get("btc_out",0) > 0 or feats.get("native_out_sum",0) > 0):
        s += 0.3
    # bursty
    if feats.get("median_dt_sec", 9999) < 30:
        s += 0.2
    # many approvals (ETH)
    if feats.get("approvals", 0) >= 5:
        s += 0.2
    # token churn with low native in (ETH)
    if feats.get("token_moves",0) >= 10 and feats.get("native_in_sum",0) == 0:
        s += 0.1
    return min(s, 1.0)

def fuse(p_ml: float, r: float) -> float:
    return 0.6*p_ml + 0.4*r

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/train")
def train():
    bundle = train_unsupervised(BTC_CSV, ETH_CSV, MODEL_PATH)
    global _bundle; _bundle = bundle
    return {"trained": True, "features": bundle.features}

@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest):
    if len(req.last20) == 0:
        raise HTTPException(400, "last20 array is required (1..20 recent tx)")

    # compute features from raw last-20
    if req.chain == "btc":
        feats = compute_btc_features([x.model_dump() for x in req.last20])
    else:
        feats = compute_eth_features([x.model_dump() for x in req.last20], approvals=req.approvals or 0)

    bundle = ensure_model()
    p_ml = score_unsupervised(bundle, feats)
    r = rule_score(feats)
    s = fuse(p_ml, r)
    risk = int(min(10, max(1, round(10*s + 0.0001))))  # clamp 1..10
    flag = risk >= FLAG_THRESHOLD

    reasons = []
    if feats.get("net_ratio",0) > 0.9 and (feats.get("btc_out",0) > 0 or feats.get("native_out_sum",0) > 0):
        reasons.append("high net outflow")
    if (feats.get("median_dt_sec",9999) < 30):
        reasons.append("bursty timing")
    if (feats.get("approvals",0) >= 5):
        reasons.append("many approvals")
    if (feats.get("token_moves",0) >= 10 and feats.get("native_in_sum",0) == 0):
        reasons.append("token churn")

    if not reasons:
        reasons.append("model anomaly")

    return ScoreResponse(chain=req.chain, risk=risk, flag=flag, reasons=reasons, features=feats)
