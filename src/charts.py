import plotly.express as px

def line_tps(df):
    fig = px.line(df, x='minute', y='txn_count', title='Transactions per Minute (sample window)')
    fig.update_layout(margin=dict(l=10,r=10,t=40,b=10))
    return fig

def line_avg_fee(df):
    fig = px.line(df, x='minute', y='avg_fee_xrp', title='Average Fee (XRP) (sample window)')
    fig.update_layout(margin=dict(l=10,r=10,t=40,b=10))
    return fig

def tradingview_widget_html(symbol: str = "BINANCE:XRPUSDT",
                            interval: str = "60",
                            studies: list[str] | None = None,
                            height: int = 600) -> str:
    """
    Generates TradingView widget HTML. Use with `st.components.v1.html(...)`.
    interval: "5","15","30","60","240","D"
    studies: e.g. ["RSI@tv-basicstudies","MACD@tv-basicstudies","Moving Average@tv-basicstudies","Moving Average Exponential@tv-basicstudies"]
    """
    if studies is None:
        studies = []
    studies_js = ",".join([f'"{s}"' for s in studies])

    return f"""
<div class="tradingview-widget-container">
  <div id="tv_chart"></div>
</div>
<script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
<script type="text/javascript">
  new TradingView.widget({{
    "width": "100%",
    "height": {int(height)},
    "symbol": "{symbol}",
    "interval": "{interval}",
    "timezone": "Etc/UTC",
    "theme": "light",
    "style": "1",
    "locale": "en",
    "toolbar_bg": "#f1f3f6",
    "enable_publishing": false,
    "withdateranges": true,
    "allow_symbol_change": true,
    "studies": [{studies_js}],
    "container_id": "tv_chart"
  }});
</script>
"""
