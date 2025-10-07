# XRP Global Payment Insights Dashboard

Beginner-friendly, read-only analytics app that visualizes XRP Ledger (XRPL) activity:
- Transactions per minute (sample window)
- Average fees (sample window)
- Recent transactions table

**Live app:** (add your Streamlit URL after deployment)

## 🚀 Quickstart
```bash
# 1) clone the repo or unzip the starter files
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## 🗂 Structure
```
xrp-insights-dashboard/
├─ README.md
├─ .gitignore
├─ requirements.txt
├─ app.py
├─ src/
│  ├─ __init__.py
│  ├─ data_ingestion.py
│  ├─ processing.py
│  ├─ charts.py
│  └─ config.py
├─ assets/
├─ .streamlit/
│  └─ config.toml
└─ tests/
   └─ test_processing.py
```

## 🧠 Notes
- Data is public & pseudonymous via XRPL explorer API.
- No wallets are deanonymized; this app is for learning only.
- Not financial advice.

## 🧭 Roadmap (nice-to-have)
- WebSocket streaming via xrpl-py
- Price/liquidity overlays
- Hourly snapshots for history
- Export CSV

**Live app:** https://<your-app-subdomain>.streamlit.app
