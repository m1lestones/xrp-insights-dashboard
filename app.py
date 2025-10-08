import time
import streamlit as st
import pandas as pd
from pathlib import Path

from src.config import REFRESH_SECONDS, TX_TABLE_ROWS
from src.data_ingestion import (
    fetch_recent_transactions,
    get_account_info, get_account_tx,
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
tab_overview, tab_explorer = st.tabs(["Overview", "Explorer"])

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

    # Demo dataset if needed
    if (df is None or df.empty) and use_demo:
        df = pd.DataFrame([
            {"hash": "DEMO1", "date_utc": pd.Timestamp.utcnow(), "amount": "25000000", "fee_drops": "12", "account": "rDEMO...", "transaction_type": "Payment"},
            {"hash": "DEMO2", "date_utc": pd.Timestamp.utcnow(), "amount": "9000000",  "fee_drops": "10", "account": "rDEMO...", "transaction_type": "Payment"},
        ])
        st.info("Showing demo data (offline mode).")

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

# ---------------------------- Safe auto-refresh ----------------------------
if auto:
    time.sleep(REFRESH_SECONDS)
    st.rerun()
