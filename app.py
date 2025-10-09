import time
import streamlit as st
import pandas as pd
from pathlib import Path

from src.config import REFRESH_SECONDS, TX_TABLE_ROWS
from src.data_ingestion import (
    fetch_recent_transactions,
    get_account_info, get_account_tx,
    get_last_endpoint,
    get_xrp_quote, get_xrp_market,
    get_server_health,            # <-- add this
)
from src.processing import compute_txn_per_minute, compute_avg_fee
from src.charts import line_tps, line_avg_fee

# set_page_config MUST be first Streamlit call
st.set_page_config(page_title="XRP Global Payment Insights", layout="wide")

# -------- Header (logo + title) --------
logo_path = Path("assets/logo.png")
if logo_path.exists():
    left, right = st.columns([0.12, 0.88])
    with left:
        st.image(str(logo_path), width=88)  # adjust 72–96 to taste
    with right:
        st.title("🌐 XRP Global Payment Insights Dashboard")
        st.caption("Read-only analytics. Data: XRPL JSON-RPC (https://s1.ripple.com:51234).")
else:
    st.title("🌐 XRP Global Payment Insights Dashboard")
    st.caption("Read-only analytics. Data: XRPL JSON-RPC (https://s1.ripple.com:51234).")

# -------- Sidebar controls --------
with st.sidebar:
    st.header("⚙️ Controls")
    auto = st.toggle("Auto-refresh", value=False, key="auto_refresh")
    st.caption(f"⏳ Every {REFRESH_SECONDS}s")
    if st.button("🔄 Refresh now"):
        st.rerun()

# -------- Tabs --------
tab_overview, tab_explorer, tab_network = st.tabs(["Overview", "Explorer", "Network"])

# ---------------------------- Overview ----------------------------
@st.cache_data(ttl=60)
def cached_recent(n=20):
    return fetch_recent_transactions(ledgers_back=n)

with tab_overview:
    colA, colB = st.columns([1, 3])
    with colA:
        use_demo = st.checkbox("Use demo data (fallback)", value=False)
    with colB:
        st.caption("Tip: enable demo data if the network is slow or rate-limited.")

    df = pd.DataFrame()
    with st.spinner("Fetching XRPL data…"):
        try:
            if not use_demo:
                df = cached_recent(20)
        except Exception as e:
            st.warning(f"XRPL fetch failed: {e}")

    # Show which node we're connected to
    st.caption(f"Connected node: {get_last_endpoint() or '—'}")

    # Demo dataset if needed
    if (df is None or df.empty) and use_demo:
        df = pd.DataFrame([
            {"hash": "DEMO1", "date_utc": pd.Timestamp.utcnow(), "amount": "25000000", "fee_drops": "12", "account": "rDEMO...", "transaction_type": "Payment"},
            {"hash": "DEMO2", "date_utc": pd.Timestamp.utcnow(), "amount": "9000000",  "fee_drops": "10", "account": "rDEMO...", "transaction_type": "Payment"},
        ])
        st.info("Showing demo data (offline mode).")

    # ----- Markets (XRP price) -----
    with st.container():
        st.subheader("📈 Market")
        quote = get_xrp_quote()
        c1, c2, c3 = st.columns([1, 2, 2])

        with c1:
            if quote and quote.get("price") is not None:
                st.metric("XRP Price (USD)", f"${quote['price']:.4f}",
                          delta=f"{quote['change_24h']:+.2f}%" if quote.get("change_24h") is not None else None)
            else:
                st.info("XRP price feed unavailable right now.")

            # RLUSD note (placeholder)
            st.caption("**RLUSD**: USD-pegged stablecoin on XRPL. Target ≈ **$1.00** (live market feed TBD).")

        with c2:
            m7 = get_xrp_market(days=7)
            if not m7.empty:
                st.caption("7-day price")
                st.line_chart(m7.set_index("ts")["price_usd"])
            else:
                st.caption("7-day price")
                st.info("No market data yet.")

        with c3:
            m30 = get_xrp_market(days=30)
            if not m30.empty:
                st.caption("30-day price")
                st.line_chart(m30.set_index("ts")["price_usd"])
            else:
                st.caption("30-day price")
                st.info("No market data yet.")

    if df is None or df.empty:
        st.error("No transactions available right now. Try **Refresh now** or enable **Demo data**.")
    else:
        # KPI cards
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Recent txns (sample)", f"{len(df):,}",
                      help="Count of successful transactions in sampled validated ledgers.")
        with col2:
            st.metric("Unique accounts (sample)", f"{df['account'].nunique():,}",
                      help="Distinct sending accounts in the sample.")
        with col3:
            fees = pd.to_numeric(df["fee_drops"], errors="coerce").dropna() / 1_000_000
            st.metric("Avg fee (sample)", f"{fees.mean():.6f} XRP" if not fees.empty else "n/a",
                      help="Average transaction fee across the sample.")

        # Charts (guarded)
        tps = compute_txn_per_minute(df)
        avg_fee = compute_avg_fee(df)

        left, right = st.columns(2)
        with left:
            if not tps.empty:
                st.plotly_chart(line_tps(tps), use_container_width=True)
            else:
                st.info("No TPS data to chart yet.")
        with right:
            if not avg_fee.empty:
                st.plotly_chart(line_avg_fee(avg_fee), use_container_width=True)
            else:
                st.info("No fee data to chart yet.")

        st.subheader("🧾 Most Recent Transactions (sample)")
        show = df[["hash", "date_utc", "amount", "fee_drops", "account", "transaction_type"]].head(TX_TABLE_ROWS)
        st.dataframe(show, use_container_width=True)

        # ---------- Whale Watch (inside the 'else' so df exists) ----------
        st.divider()
        st.subheader("🐳 Whale Watch (large XRP transfers)")

        # Threshold slider (XRP)
        thr_xrp = st.slider(
            "Show transfers above (XRP)",
            min_value=100.0, max_value=5_000_000.0, value=100_000.0, step=100.0,
            help="Filters for XRP-denominated transfers by XRP amount (issued currencies are ignored)."
        )

        # Normalize 'amount' (drops → XRP). Issued currencies (dict/string) are ignored.
        ww = df.copy()
        amt_num = pd.to_numeric(ww["amount"], errors="coerce")  # drops (if XRP)
        ww["amount_xrp"] = amt_num / 1_000_000

        whales = (
            ww.loc[ww["amount_xrp"].notna() & (ww["amount_xrp"] >= thr_xrp)]
              .sort_values("amount_xrp", ascending=False)
              .head(50)
              .copy()
        )

        if whales.empty:
            st.info("No XRP transfers above that threshold in the sampled ledgers.")
        else:
            # Optional: short hash preview
            whales["hash_preview"] = whales["hash"].str.slice(0, 10) + "…"

            cols = ["date_utc", "account", "transaction_type", "amount_xrp", "hash_preview"]
            st.dataframe(
                whales[cols].rename(columns={
                    "date_utc": "When (UTC)",
                    "account": "From",
                    "transaction_type": "Type",
                    "amount_xrp": "Amount (XRP)",
                    "hash_preview": "Tx Hash",
                }),
                use_container_width=True,
                hide_index=True,
            )

            # Quick export for your presentation
            csv_whales = whales[["hash", "date_utc", "account", "transaction_type", "amount_xrp"]].to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download whale transfers (CSV)", csv_whales, "whale_transfers.csv", "text/csv")

# ---------------------------- Explorer ----------------------------
with tab_explorer:
    st.subheader("🔎 Address Explorer")
    st.caption("Enter an XRP (classic) address starting with 'r' to view balance & recent transactions.")
    addr = st.text_input("XRP address", placeholder="r...")
    limit = st.number_input("Recent txns to load", min_value=5, max_value=200, value=20, step=5)

    if st.button("Lookup"):
        if not addr or not addr.startswith("r"):
            st.error("Please enter a valid classic address that starts with 'r'.")
        else:
            with st.spinner("Fetching account info & transactions..."):
                try:
                    info = get_account_info(addr)
                    if "account_data" in info:
                        ad = info["account_data"]
                        xrp_balance = float(ad.get("Balance", 0)) / 1_000_000
                        c1, c2, c3 = st.columns(3)
                        c1.metric("XRP Balance", f"{xrp_balance:,.6f} XRP")
                        c2.metric("Sequence", ad.get("Sequence", "—"))
                        c3.metric("OwnerCount", ad.get("OwnerCount", "—"))
                        with st.expander("Raw account_data"):
                            st.json(ad)
                    else:
                        st.warning(info.get("error_message") or "No account data returned.")

                    txs = get_account_tx(addr, limit=int(limit))
                    if txs:
                        rows = []
                        for t in txs:
                            tx = t.get("tx", {}) or {}
                            meta = t.get("meta", {}) or {}
                            res = meta.get("TransactionResult")
                            amt = tx.get("Amount")
                            if isinstance(amt, dict):
                                amount_disp = amt.get("value")
                            else:
                                try:
                                    # normalize to XRP if numeric in drops
                                    amount_disp = float(amt) / 1_000_000 if amt is not None else None
                                except Exception:
                                    amount_disp = amt
                            try:
                                fee_xrp = float(tx.get("Fee")) / 1_000_000 if tx.get("Fee") is not None else None
                            except Exception:
                                fee_xrp = tx.get("Fee")
                            rows.append({
                                "hash": tx.get("hash"),
                                "type": tx.get("TransactionType"),
                                "result": res,
                                "amount_xrp_or_value": amount_disp,
                                "fee_xrp": fee_xrp,
                                "account": tx.get("Account"),
                            })
                        st.write("Recent Transactions")
                        st.dataframe(pd.DataFrame(rows), use_container_width=True)
                    else:
                        st.info("No recent transactions found.")
                except Exception as e:
                    st.error("Lookup failed.")
                    st.caption(str(e))

# ---------------------------- Network ----------------------------
with tab_network:
    st.subheader("🩺 Ledger Health")

    @st.cache_data(ttl=30)
    def cached_health():
        return get_server_health()

    h = cached_health()
    info = h.get("info", {})
    fee = h.get("fee", {})

    # Parse common fields safely
    server_state = info.get("server_state", "—")
    peers = info.get("peers", "—")
    load_factor = info.get("load_factor", "—")
    validated = info.get("validated_ledger", {}) or {}
    seq = validated.get("seq", "—")
    complete_ledgers = info.get("complete_ledgers", "—")

    drops = (fee.get("drops") or {}) if isinstance(fee, dict) else {}
    base_fee_drops = drops.get("base_fee")
    base_fee_xrp = None
    try:
        if base_fee_drops is not None:
            base_fee_xrp = float(base_fee_drops) / 1_000_000
    except Exception:
        pass

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Server state", server_state)
    with c2:
        st.metric("Peers", str(peers))
    with c3:
        st.metric("Load factor", str(load_factor))
    with c4:
        st.metric("Validated ledger", str(seq))

    c5, c6 = st.columns([2, 2])
    with c5:
        st.caption(f"Connected node: **{get_last_endpoint() or '—'}**")
        st.write("Complete ledgers:")
        st.code(str(complete_ledgers), language="text")
    with c6:
        if base_fee_xrp is not None:
            st.metric("Base fee (XRP)", f"{base_fee_xrp:.6f}")
        else:
            st.info("Fee info unavailable.")

    with st.expander("Raw server_info / fee JSON"):
        if "info_error" in h:
            st.error(f"server_info error: {h['info_error']}")
        else:
            st.json(info)
        if "fee_error" in h:
            st.error(f"fee error: {h['fee_error']}")
        else:
            st.json(fee)

# ---------------------------- Safe auto-refresh ----------------------------
if auto:
    time.sleep(REFRESH_SECONDS)
    st.rerun()
