from datetime import datetime, timezone
import pandas as pd
import requests

# Multiple XRPL JSON-RPC endpoints for resilience
ENDPOINTS = [
    "https://s1.ripple.com:51234",   # Ripple public node
    "https://s2.ripple.com:51234",   # Ripple backup
    "https://xrplcluster.com/",      # Community aggregator
]

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "XRP-Insights/0.2",
}

def _rpc(method: str, params: dict) -> dict:
    """Call XRPL JSON-RPC with simple endpoint rotation."""
    last_err = None
    for url in ENDPOINTS:
        try:
            r = requests.post(
                url,
                json={"method": method, "params": [params]},
                headers=HEADERS,
                timeout=15,
            )
            r.raise_for_status()
            res = r.json()
            if "result" in res:
                return res["result"]
            # If shape is unexpected, try next endpoint
            last_err = RuntimeError(f"Bad RPC from {url}: {res}")
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"All XRPL endpoints failed. Last error: {last_err}")

def _to_utc(close_time_human: str | None, close_time_unix: int | None):
    """Best-effort convert ledger time to aware UTC datetime."""
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
    """Fetch a recent sample of successful transactions from validated ledgers."""
    try:
        info = _rpc("server_info", {})
        latest = info.get("info", {}).get("validated_ledger", {}).get("seq")
        if latest is None:
            # Fallback: try to parse complete_ledgers like "79100000-79100500"
            cl = info.get("info", {}).get("complete_ledgers")
            if isinstance(cl, str) and "-" in cl:
                try:
                    latest = int(cl.split("-")[-1])
                except Exception:
                    pass
        if latest is None:
            return pd.DataFrame(columns=["hash", "date_utc", "amount", "fee_drops", "account", "transaction_type"])
    except Exception:
        # If server_info fails entirely, return empty
        return pd.DataFrame(columns=["hash", "date_utc", "amount", "fee_drops", "account", "transaction_type"])

    rows = []
    for idx in range(latest, latest - max(1, ledgers_back), -1):
        try:
            res = _rpc("ledger", {"ledger_index": str(idx), "transactions": True, "expand": True, "binary": False})
        except Exception:
            continue
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

# ---- Address Explorer helpers ----
def get_account_info(address: str) -> dict:
    """Return account_info.result (contains 'account_data' on success)."""
    return _rpc("account_info", {
        "account": address,
        "ledger_index": "validated",
        "strict": True
    })

def get_account_tx(address: str, limit: int = 20) -> list[dict]:
    """Return list from account_tx.result.transactions (may be empty)."""
    res = _rpc("account_tx", {
        "account": address,
        "limit": int(limit),
        "ledger_index_min": -1,
        "ledger_index_max": -1
    })
    return res.get("transactions", []) or []
