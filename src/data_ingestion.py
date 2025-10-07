# src/data_ingestion.py
from datetime import datetime, timezone
import pandas as pd
import requests

JSON_RPC_URL = "https://s1.ripple.com:51234"
HEADERS = {"Content-Type": "application/json", "User-Agent": "XRP-Insights/0.1"}

def _rpc(method: str, params: dict) -> dict:
    r = requests.post(JSON_RPC_URL, json={"method": method, "params": [params]}, headers=HEADERS, timeout=20)
    r.raise_for_status()
    res = r.json()
    if "result" not in res:
        raise RuntimeError(f"Bad RPC response: {res}")
    return res["result"]

def _to_utc(close_time_human: str | None, close_time_unix: int | None):
    if close_time_human:
        try:
            return pd.to_datetime(close_time_human, utc=True).to_pydatetime()
        except Exception:
            pass
    try:
        return datetime.utcfromtimestamp(int(close_time_unix or 0)).replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.utcnow().replace(tzinfo=timezone.utc)

def fetch_recent_transactions(ledgers_back: int = 20) -> pd.DataFrame:
    info = _rpc("server_info", {})
    latest = info.get("info", {}).get("validated_ledger", {}).get("seq")
    if latest is None:
        return pd.DataFrame(columns=["hash","date_utc","amount","fee_drops","account","transaction_type"])

    rows = []
    for idx in range(latest, latest - max(1, ledgers_back), -1):
        res = _rpc("ledger", {"ledger_index": str(idx), "transactions": True, "expand": True, "binary": False})
        lgr = res.get("ledger", {}) or {}
        dt = _to_utc(lgr.get("close_time_human"), lgr.get("close_time"))
        for tx in lgr.get("transactions", []) or []:
            meta = tx.get("metaData", {}) or {}
            if meta.get("TransactionResult") != "tesSUCCESS":
                continue
            amt = tx.get("Amount")
            amount_value = amt.get("value") if isinstance(amt, dict) else amt
            rows.append({
                "hash": tx.get("hash"),
                "date_utc": dt,
                "amount": amount_value,
                "fee_drops": tx.get("Fee"),
                "account": tx.get("Account"),
                "transaction_type": tx.get("TransactionType"),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date_utc"] = pd.to_datetime(df["date_utc"], utc=True, errors="coerce")
    return df
# ---- Address Explorer helpers (append to bottom) ----
def get_account_info(address: str) -> dict:
    """
    Returns account_info.result (contains 'account_data' on success).
    Requires the helper _rpc(method, params) defined above.
    """
    return _rpc("account_info", {
        "account": address,
        "ledger_index": "validated",
        "strict": True
    })

def get_account_tx(address: str, limit: int = 20) -> list[dict]:
    """
    Returns a list from account_tx.result.transactions (may be empty).
    """
    res = _rpc("account_tx", {
        "account": address,
        "limit": int(limit),
        "ledger_index_min": -1,
        "ledger_index_max": -1
    })
    return res.get("transactions", []) or []
