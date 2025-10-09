# src/processing.py
import pandas as pd

def compute_txn_per_minute(df: pd.DataFrame) -> pd.DataFrame:
    """Group transactions per minute for a simple TPS-like view."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["minute", "txn_count"])
    s = df.copy()
    s["date_utc"] = pd.to_datetime(s["date_utc"], utc=True, errors="coerce")
    s["minute"] = s["date_utc"].dt.floor("min")  # <- modern alias (replaces 'T')
    out = s.groupby("minute").size().rename("txn_count").reset_index()
    return out.sort_values("minute")

def compute_avg_fee(df: pd.DataFrame) -> pd.DataFrame:
    """Average fee (in XRP) per minute."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["minute", "avg_fee_xrp"])
    s = df.copy()
    s["fee_xrp"] = pd.to_numeric(s.get("fee_drops"), errors="coerce") / 1_000_000  # drops → XRP
    s["date_utc"] = pd.to_datetime(s["date_utc"], utc=True, errors="coerce")
    s["minute"] = s["date_utc"].dt.floor("min")  # <- modern alias (replaces 'T')
    out = s.groupby("minute")["fee_xrp"].mean().reset_index(name="avg_fee_xrp")
    return out.sort_values("minute")
