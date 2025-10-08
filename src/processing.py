import pandas as pd

def compute_txn_per_minute(df: pd.DataFrame) -> pd.DataFrame:
    """Group successful transactions by minute."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["minute", "txn_count"])
    s = df.copy()
    s["date_utc"] = pd.to_datetime(s["date_utc"], utc=True, errors="coerce")
    s["minute"] = s["date_utc"].dt.floor("min")  # 'T' deprecated → use 'min'
    s = s.dropna(subset=["minute"])
    out = s.groupby("minute").size().rename("txn_count").reset_index()
    return out.sort_values("minute")

def compute_avg_fee(df: pd.DataFrame) -> pd.DataFrame:
    """Average fee (in XRP) by minute."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["minute", "avg_fee_xrp"])
    s = df.copy()
    s["fee_xrp"] = pd.to_numeric(s["fee_drops"], errors="coerce") / 1_000_000  # drops → XRP
    s["date_utc"] = pd.to_datetime(s["date_utc"], utc=True, errors="coerce")
    s["minute"] = s["date_utc"].dt.floor("min")  # 'T' deprecated → use 'min'
    s = s.dropna(subset=["minute", "fee_xrp"])
    out = s.groupby("minute")["fee_xrp"].mean().reset_index(name="avg_fee_xrp")
    return out.sort_values("minute")

