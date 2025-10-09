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

LAST_ENDPOINT = None  # track last successful node

def get_last_endpoint() -> str | None:
    return LAST_ENDPOINT

def _rpc(method: str, params: dict) -> dict:
    """Call XRPL JSON-RPC with simple endpoint rotation."""
    global LAST_ENDPOINT
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
                LAST_ENDPOINT = url
                return res["result"]
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
            cl = info.get("info", {}).get("complete_ledgers")
            if isinstance(cl, str) and "-" in cl:
                try:
                    latest = int(cl.split("-")[-1])
                except Exception:
                    pass
        if latest is None:
            return pd.DataFrame(columns=["hash", "date_utc", "amount", "fee_drops", "account", "transaction_type"])
    except Exception:
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
    return _rpc("account_info", {
        "account": address,
        "ledger_index": "validated",
        "strict": True
    })

def get_account_tx(address: str, limit: int = 20) -> list[dict]:
    res = _rpc("account_tx", {
        "account": address,
        "limit": int(limit),
        "ledger_index_min": -1,
        "ledger_index_max": -1
    })
    return res.get("transactions", []) or []

# --- Markets: XRP price from CoinGecko ---

def get_xrp_quote() -> dict | None:
    """
    Returns {'price': float, 'change_24h': float} or None on failure.
    """
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": "ripple", "vs_currencies": "usd", "include_24hr_change": "true"}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json().get("ripple") or {}
        return {
            "price": float(data.get("usd")) if data.get("usd") is not None else None,
            "change_24h": float(data.get("usd_24h_change")) if data.get("usd_24h_change") is not None else None,
        }
    except Exception:
        return None

def get_xrp_market(days: int = 7) -> pd.DataFrame:
    """
    Returns a DataFrame with columns ['ts','price_usd'] for the last N days.
    """
    try:
        url = "https://api.coingecko.com/api/v3/coins/ripple/market_chart"
        params = {"vs_currency": "usd", "days": int(days)}
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        prices = pd.DataFrame(data.get("prices") or [], columns=["ts", "price_usd"])
        if prices.empty:
            return prices
        prices["ts"] = pd.to_datetime(prices["ts"], unit="ms", utc=True)
        return prices
    except Exception:
        return pd.DataFrame(columns=["ts", "price_usd"])

# --- Ledger / Server health helpers -----------------------------------------
def get_server_health() -> dict:
    """
    Fetch XRPL server info and fee data.
    Returns a dict. Missing pieces are noted with *_error so the UI can show gracefully.
    """
    out: dict = {}
    try:
        info = _rpc("server_info", {})
        out["info"] = info.get("info", {}) or {}
    except Exception as e:
        out["info_error"] = str(e)

    try:
        fee = _rpc("fee", {})
        out["fee"] = fee or {}
    except Exception as e:
        out["fee_error"] = str(e)

    return out
