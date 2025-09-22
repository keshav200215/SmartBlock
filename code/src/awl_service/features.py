# src/awl_service/features.py
import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

def _parse_ts(ts: str) -> float:
    # robust: handle “UTC” suffix or plain ISO
    ts = ts.replace(" UTC", "")
    try:
        return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()

def _median_dt_seconds(ts_list: List[str]) -> float:
    if len(ts_list) < 2:
        return 0.0
    arr = sorted(_parse_ts(t) for t in ts_list)
    dts = np.diff(arr)
    if len(dts) == 0:
        return 0.0
    return float(np.median(dts))

def compute_btc_features(last20: List[Dict[str, Any]]) -> Dict[str, float]:
    moves = len(last20)
    in_count = sum(1 for r in last20 if not r.get("is_input", False))    # incoming on BTC = outputs view
    out_count = sum(1 for r in last20 if r.get("is_input", False))
    btc_in = sum(float(r.get("amount_btc") or 0.0) for r in last20 if not r.get("is_input", False))
    btc_out = sum(float(r.get("amount_btc") or 0.0) for r in last20 if r.get("is_input", False))
    net_btc = btc_in - btc_out
    denom = btc_in + btc_out
    net_ratio = abs(net_btc) / denom if denom > 0 else 0.0
    median_dt_sec = _median_dt_seconds([r["block_timestamp"] for r in last20])

    return {
        "moves": float(moves),
        "in_count": float(in_count),
        "out_count": float(out_count),
        "btc_in": float(btc_in),
        "btc_out": float(btc_out),
        "net_btc": float(net_btc),
        "net_ratio": float(net_ratio),
        "median_dt_sec": float(median_dt_sec),
        # placeholders to align with model feature set
        "native_in_sum": 0.0, "native_out_sum": 0.0, "native_net": 0.0,
        "token_moves": 0.0, "tokens_touched": 0.0, "approvals": 0.0,
    }

def compute_eth_features(last20: List[Dict[str, Any]], approvals: int = 0) -> Dict[str, float]:
    moves = len(last20)
    # direction by from/to
    in_count = sum(1 for r in last20 if r.get("to_addr"))
    out_count = sum(1 for r in last20 if r.get("from_addr"))
    native_in_sum = sum(float(r.get("native_value") or 0.0) for r in last20 if r.get("to_addr"))
    native_out_sum = sum(float(r.get("native_value") or 0.0) for r in last20 if r.get("from_addr"))
    native_net = native_in_sum - native_out_sum
    denom = native_in_sum + native_out_sum
    net_ratio = abs(native_net) / denom if denom > 0 else 0.0
    token_moves = sum(1 for r in last20 if r.get("token_address"))
    tokens_touched = len({r.get("token_address") for r in last20 if r.get("token_address")})
    median_dt_sec = _median_dt_seconds([r["block_timestamp"] for r in last20])

    return {
        "moves": float(moves),
        "in_count": float(in_count),
        "out_count": float(out_count),
        "native_in_sum": float(native_in_sum),
        "native_out_sum": float(native_out_sum),
        "native_net": float(native_net),
        "net_ratio": float(net_ratio),
        "token_moves": float(token_moves),
        "tokens_touched": float(tokens_touched),
        "median_dt_sec": float(median_dt_sec),
        "approvals": float(approvals or 0),
        # BTC placeholders for a unified feature list
        "btc_in": 0.0, "btc_out": 0.0, "net_btc": 0.0,
    }
