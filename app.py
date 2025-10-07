import streamlit as st
import pandas as pd

from src.config import REFRESH_SECONDS, TX_TABLE_ROWS
from src.data_ingestion import fetch_recent_transactions
from src.processing import compute_txn_per_minute, compute_avg_fee
from src.charts import line_tps, line_avg_fee

st.set_page_config(page_title="XRP Global Payment Insights", layout="wide")

st.title("🌐 XRP Global Payment Insights Dashboard")
st.caption("Read-only analytics. Data: XRPL JSON-RPC (https://s1.ripple.com:51234).")

with st.sidebar:
    st.header("⚙️ Controls")
    st.write(f"⏳ Auto-refresh every {REFRESH_SECONDS}s (click the 🔄 button to refresh now)")
    if st.button("🔄 Refresh now"):
        st.rerun()

# Fetch a recent sample from XRPL
df = fetch_recent_transactions(ledgers_back=20)

# Graceful empty state
if df is None or df.empty:
    st.warning("No transactions fetched yet. Try the refresh button and wait a few seconds.")
    st.stop()

# KPI cards
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Recent txns (sample)", f"{len(df):,}")
with col2:
    st.metric("Unique accounts (sample)", f"{df['account'].nunique():,}")
with col3:
    fees = pd.to_numeric(df["fee_drops"], errors="coerce").dropna() / 1_000_000
    st.metric("Avg fee (sample)", f"{fees.mean():.6f} XRP" if not fees.empty else "n/a")

# Charts
tps = compute_txn_per_minute(df)
avg_fee = compute_avg_fee(df)

left, right = st.columns(2)
with left:
    st.plotly_chart(line_tps(tps), use_container_width=True)
with right:
    st.plotly_chart(line_avg_fee(avg_fee), use_container_width=True)

st.subheader("🧾 Most Recent Transactions (sample)")
show = df[["hash", "date_utc", "amount", "fee_drops", "account", "transaction_type"]].head(TX_TABLE_ROWS)
st.dataframe(show, use_container_width=True)


# Auto refresh
st.autorefresh(interval=REFRESH_SECONDS * 1000, key="auto_refresh_key")
