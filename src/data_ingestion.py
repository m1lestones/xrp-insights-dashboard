# src/data_ingestion.py
from datetime import datetime, timezone
from typing import List
import pandas as pd

from xrpl.clients import JsonRpcClient
from xrpl.models.requests import ServerInfo, Ledger

# Public JSON-RPC endpoint run by Ripple
JSON_RPC_URL = "https://s1.ripple.com:51234"

def _to_utc(ts_human: str, fallback_unix: int) -> datetime:
    """
    XRPL JSON-RPC returns ledger 'close_time_human' like '2025-Jun-30 12:34:56.000000000 UTC'.
    If missing, fall back to unix seconds.
    """
    if ts_human:
        try:
            # Let pandas parse the human timestamp robustly
            dt = pd.to_datetime(ts_human, utc=True)
            return dt.to_pydatetime()
        except Exception:
            pass
    # Fallback: unix seconds
    return datetime.utcfromtimestamp(int(fallback_unix)).replace(tzinfo=timezone.utc)

def _extract_amount(tx: dict) -> str:
    """
    Payment Amount can be a string (drops) or an object (issued currency).
    For non-Payment types, there may be no 'Amount'.
    """
    amt = tx.get("Amount")
    if isinstance(amt, dict):
        # issued currency: {"currency": "USD", "issuer": "...", "value": "123.45"}
        return amt.get("value")
    return amt  # string or None

def fetch_recent_transactions(ledgers_back: int = 20) -> pd.DataFrame:
    """
    Pull transactions from the last N validated ledgers via JSON-RPC.
    Returns a DataFrame: hash, date_utc, amount, fee_drops, account, transaction_type
    """
    client = JsonRpcClient(JSON_RPC_URL)

    # 1) Find latest validated ledger index
    info = client.request(ServerInfo())
    vinfo = info.result["info"].get("validated_ledger", {})
    latest_index = vinfo.get("seq")
    if latest_index is None:
        return pd.DataFrame(columns=["hash","date_utc","amount","fee_drops","account","transaction_type"])

    rows: List[dict] = []

    # 2) Walk backwards N ledgers and collect transactions
    for ledger_index in range(latest_index, latest_index - max(1, ledgers_back), -1):
        req = Ledger(
            ledger_index=str(ledger_index),
            transactions=True,
            expand=True,     # include full tx JSON
            binary=False
        )
        resp = client.request(req).result
        lgr = resp.get("ledger", {})

        # Prefer human string, else fallback to numeric
        close_human = lgr.get("close_time_human")
        close_unix = lgr.get("close_time", 0)
        close_dt = _to_utc(close_human, close_unix)

        txs = lgr.get("transactions", [])
        if not isinstance(txs, list):
            continue

        for tx in txs:
            # Two shapes are possible; 'metaData' contains result code
            meta = tx.get("metaData", {})
            result = meta.get("TransactionResult")
            if result != "tesSUCCESS":
                continue

            rows.append({
                "hash": tx.get("hash"),
                "date_utc": close_dt,
                "amount": _extract_amount(tx),
                "fee_drops": tx.get("Fee"),
                "account": tx.get("Account"),
                "transaction_type": tx.get("TransactionType"),
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        # Ensure tz-aware UTC
        df["date_utc"] = pd.to_datetime(df["date_utc"], utc=True, errors="coerce")
    return df
