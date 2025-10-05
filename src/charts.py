import plotly.express as px

def line_tps(df):
    fig = px.line(df, x='minute', y='txn_count', title='Transactions per Minute (sample window)')
    fig.update_layout(margin=dict(l=10,r=10,t=40,b=10))
    return fig

def line_avg_fee(df):
    fig = px.line(df, x='minute', y='avg_fee_xrp', title='Average Fee (XRP) (sample window)')
    fig.update_layout(margin=dict(l=10,r=10,t=40,b=10))
    return fig
