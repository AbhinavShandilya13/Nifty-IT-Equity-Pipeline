import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="NIFTY IT Research | Pipeline Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

TICKERS = ["INFY.NS", "TECHM.NS", "WIPRO.NS", "HCLTECH.NS"]
SECTOR_LABEL = "IT services"

TICKER_NAMES = {
    "INFY.NS": "Infosys",
    "TECHM.NS": "Tech Mahindra",
    "WIPRO.NS": "Wipro",
    "HCLTECH.NS": "HCLTech",
}

POSITIVE = "#78b874"
NEGATIVE = "#d98a7a"
ACCENT = "#5f9c5c"
MUTED = "#a9c2bf"
BENCHMARK = "#6f8b88"

# ----------------------------------------------------------------------------
# GLOBAL CSS THEME
# ----------------------------------------------------------------------------
GLOBAL_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root { --bg-0:#0a2023; --bg-1:#0d2b2e; --card:#123338; --card-border:rgba(150,190,185,0.14); --line:rgba(150,190,185,0.08); --text-hi:#eef5f3; --text-mid:#a9c2bf; --text-lo:#6f8b88; --green:#5f9c5c; --green-hi:#78b874; --red:#a85a4a; }
header[data-testid="stHeader"] { display: none; }
section[data-testid="stSidebar"] { display: none; }
.block-container { padding-top: 2rem !important; padding-bottom: 4rem !important; max-width: 1200px !important; }
.stApp { background: repeating-linear-gradient(115deg, rgba(150,190,185,0.035) 0px, rgba(150,190,185,0.035) 1px, transparent 1px, transparent 90px), linear-gradient(180deg, var(--bg-1), var(--bg-0) 60%) !important; background-color: var(--bg-0) !important; font-family: 'Inter', sans-serif !important; color: var(--text-hi) !important; }
h1, h2, h3 { font-family: 'Oswald', sans-serif !important; color: var(--text-hi) !important; }
div[data-testid="stTabs"] button { font-family: 'Oswald', sans-serif; font-size: 20px; letter-spacing: 1px; color: var(--text-lo); }
div[data-testid="stTabs"] button[aria-selected="true"] { color: var(--green-hi) !important; border-bottom-color: var(--green-hi) !important; }
.top-bar { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--card-border); padding-bottom: 15px; margin-bottom: 30px; }
.brand { font-family: 'Oswald', sans-serif; font-size: 24px; font-weight: 600; letter-spacing: 2px; }
.status-pill { display: inline-flex; align-items: center; gap: 8px; background: linear-gradient(180deg, var(--green-hi), var(--green)); color: #0a1f10; font-family: 'Inter', sans-serif; font-weight: 700; font-size: 13px; letter-spacing: 0.5px; padding: 6px 16px; border-radius: 999px; }
.status-pill .dot { width: 8px; height: 8px; border-radius: 50%; background: #0a1f10; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.35;} }
.hero { background: rgba(10,32,35,0.4); border: 1px solid var(--card-border); border-radius: 16px; padding: 30px; margin-bottom: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
.hero-eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--green-hi); text-transform: uppercase; letter-spacing: 2px; margin-bottom: 10px; }
.hero h1 { margin-top: 0; font-size: 32px; line-height: 1.3; max-width: 800px; }
.hero p { color: var(--text-mid); font-size: 15px; line-height: 1.6; max-width: 800px; margin-bottom: 20px; }
.hero-stack { display: flex; gap: 12px; flex-wrap: wrap; font-family: 'JetBrains Mono', monospace; font-size: 11px; }
.hero-stack span { background: rgba(150,190,185,0.08); border: 1px solid var(--card-border); padding: 4px 10px; border-radius: 4px; color: var(--text-mid); }
.kpi-card { background-color: var(--card); border-radius: 14px; padding: 20px; border: 1px solid var(--card-border); box-shadow: 0 4px 15px rgba(0,0,0,0.1); height: 100%; }
.kpi-label { font-family: 'JetBrains Mono', monospace; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; color: var(--text-lo); margin-bottom: 8px; }
.kpi-value { font-family: 'Oswald', sans-serif; font-size: 32px; font-weight: 600; color: var(--text-hi); }
.footer { margin-top: 60px; padding-top: 20px; border-top: 1px solid var(--card-border); display: flex; justify-content: space-between; align-items: center; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-lo); }
.footer a { color: var(--green-hi); text-decoration: none; margin-left: 15px; font-weight: 600; transition: color 0.2s; }
.footer a:hover { color: var(--text-hi); }
@media (max-width: 768px) {
  .hero { padding: 20px; }
  .hero h1 { font-size: 24px; }
  .top-bar { flex-direction: column; align-items: flex-start; gap: 12px; }
  .footer { flex-direction: column; gap: 12px; text-align: center; }
  .footer a { margin-left: 0; margin: 0 10px; }
}
</style>
"""
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# DB CONNECTION & DATA FETCHING
# ----------------------------------------------------------------------------
@st.cache_resource
def get_engine():
    load_dotenv()
    db_url = URL.create(
        drivername="postgresql",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME")
    )
    return create_engine(db_url, pool_pre_ping=True)

engine = get_engine()

@st.cache_data(ttl=300)
def load_price_history(ticker: str, days: int = 30) -> pd.DataFrame:
    query = text("""
        SELECT date, close_price as close, rolling_7d_avg, data_status
        FROM analytics_summary
        WHERE ticker = :ticker
        ORDER BY date DESC
        LIMIT :days
    """)
    df = pd.read_sql(query, engine, params={"ticker": ticker, "days": days})
    return df.sort_values("date").reset_index(drop=True)

@st.cache_data(ttl=300)
def load_latest_metrics(ticker: str) -> pd.Series:
    query = text("""
        SELECT close_price as close, rolling_7d_avg, net_profit_margin_pct, pe_ratio, date, data_status
        FROM analytics_summary
        WHERE ticker = :ticker
        ORDER BY date DESC
        LIMIT 1
    """)
    df = pd.read_sql(query, engine, params={"ticker": ticker})
    return df.iloc[0] if not df.empty else pd.Series(dtype="float64")

@st.cache_data(ttl=300)
def load_sector_index(days: int = 30) -> pd.DataFrame:
    query = text("""
        SELECT date, AVG(close_price) AS sector_avg_close
        FROM analytics_summary
        WHERE ticker = ANY(:tickers)
        GROUP BY date
        ORDER BY date DESC
        LIMIT :days
    """)
    df = pd.read_sql(query, engine, params={"tickers": TICKERS, "days": days})
    return df.sort_values("date").reset_index(drop=True)

@st.cache_data(ttl=60)
def load_pipeline_status() -> pd.Series:
    query = text("SELECT execution_time, status FROM pipeline_logs ORDER BY run_id DESC LIMIT 1")
    df = pd.read_sql(query, engine)
    return df.iloc[0] if not df.empty else pd.Series(dtype="object")

# ----------------------------------------------------------------------------
# TOP BAR & HERO SECTION
# ----------------------------------------------------------------------------
pipeline = load_pipeline_status()
sync_text = "UNKNOWN"
if not pipeline.empty:
    run_time = pd.to_datetime(pipeline["execution_time"])
    age_minutes = (datetime.now() - run_time).total_seconds() / 60 if run_time.tzinfo is None else (datetime.now(timezone.utc) - run_time).total_seconds() / 60
    age_minutes = max(0, age_minutes)
    if age_minutes < 60:
        sync_text = f"SYNCED {int(age_minutes)}M AGO"
    else:
        sync_text = f"SYNCED {int(age_minutes // 60)}H AGO"

st.markdown(f"""
<div class="top-bar">
    <div class="brand">NIFTY IT RESEARCH</div>
    <div class="status-pill"><span class="dot"></span>LIVE · {sync_text}</div>
</div>
<div class="hero">
    <div class="hero-eyebrow">Data Engineering Portfolio Project</div>
    <h1>Transparent, auditable data pipeline tracking India's largest IT companies.</h1>
    <p>This is a completely automated ETL pipeline. Data is extracted nightly via <b>Apache Airflow</b>, structurally graded for quality (handling API outages and market halts), transformed with <b>Pandas</b>, and Upserted into a <b>PostgreSQL</b> data warehouse. No manual entries, no black-box AI — just pure, fault-tolerant engineering.</p>
    <div class="hero-stack">
        <span>YFINANCE</span>
        <span>PYTHON 3</span>
        <span>POSTGRESQL</span>
        <span>APACHE AIRFLOW</span>
        <span>STREAMLIT</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# TABBED TICKER VIEW
# ----------------------------------------------------------------------------
tabs = st.tabs([ticker.replace(".NS", "") for ticker in TICKERS])
sector_index = load_sector_index(days=30)

for idx, ticker in enumerate(TICKERS):
    with tabs[idx]:
        st.markdown("<br>", unsafe_allow_html=True)
        
        latest = load_latest_metrics(ticker)
        history = load_price_history(ticker, days=30)

        if latest.empty or history.empty:
            st.warning(f"No recent data found for {ticker}.")
            continue

        # Data Quality Alerts
        status = latest.get('data_status', 'ACTUAL')
        if status == 'IMPUTED_API_OUTAGE':
            st.error("⚠️ **DATA PROVENANCE ALERT:** Today's upstream API response was empty. The price shown has been mathematically forward-filled to maintain series continuity.")
        elif status == 'MARKET_HALT':
            st.warning("⏸️ **DATA PROVENANCE ALERT:** Trading volume was 0 today. The asset was halted or the market was closed.")

        if len(history) >= 2:
            prev_close = history["close"].iloc[-2]
            latest_close = history["close"].iloc[-1]
            close_delta_pct = ((latest_close - prev_close) / prev_close) * 100
        else:
            close_delta_pct = 0.0

        # KPI Cards
        col1, col2, col3 = st.columns(3)

        with col1:
            arrow = "▲" if close_delta_pct >= 0 else "▼"
            color = POSITIVE if close_delta_pct >= 0 else NEGATIVE
            
            st.markdown(f'''
                <div class="kpi-card">
                    <div class="kpi-label">Latest Close Price</div>
                    <div class="kpi-value">₹{latest["close"]:,.2f}</div>
                    <div style="margin-top: 8px; color:{color}; font-size:14px; font-weight:600;">{arrow} {abs(close_delta_pct):.2f}%</div>
                </div>
            ''', unsafe_allow_html=True)

        with col2:
            st.markdown(f'''
                <div class="kpi-card">
                    <div class="kpi-label">P/E Ratio</div>
                    <div class="kpi-value">{latest["pe_ratio"]:.2f}</div>
                </div>
            ''', unsafe_allow_html=True)

        with col3:
            st.markdown(f'''
                <div class="kpi-card">
                    <div class="kpi-label">Net Profit Margin</div>
                    <div class="kpi-value">{latest["net_profit_margin_pct"]:.2f}%</div>
                </div>
            ''', unsafe_allow_html=True)

        # Main Chart
        st.markdown("<br><h4 style='font-family: Oswald, sans-serif; color: var(--text-mid); font-weight: 400; font-size: 18px;'>PRICE TREND VS 7-DAY ROLLING AVERAGE</h4>", unsafe_allow_html=True)

        y_min = min(history["close"].min(), history["rolling_7d_avg"].min()) * 0.97
        y_max = max(history["close"].max(), history["rolling_7d_avg"].max()) * 1.03

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=history["date"], y=history["close"], mode="lines", name="Close Price",
            line=dict(color=POSITIVE, width=2.5), fill="tozeroy", fillcolor="rgba(120, 184, 116, 0.08)"
        ))
        fig.add_trace(go.Scatter(
            x=history["date"], y=history["rolling_7d_avg"], mode="lines", name="7-Day Avg",
            line=dict(color=MUTED, width=1.5, dash="dash")
        ))
        if not sector_index.empty:
            fig.add_trace(go.Scatter(
                x=sector_index["date"], y=sector_index["sector_avg_close"], mode="lines", name="Sector Index",
                line=dict(color=BENCHMARK, width=1.5, dash="dot"), opacity=0.7
            ))

        fig.update_layout(
            height=420, margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#a9c2bf", family="Inter"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(showgrid=False, color="#6f8b88"),
            yaxis=dict(range=[y_min, y_max], showgrid=True, gridcolor="rgba(150,190,185,0.08)", color="#6f8b88"),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=f"chart_{ticker}")

# ----------------------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------------------
st.markdown("""
<div class="footer">
    <div>NIFTY IT Research Pipeline · Created by Abhinav Shandilya</div>
    <div>
        <a href="https://github.com/AbhinavShandilya13" target="_blank">GITHUB</a>
        <a href="https://www.linkedin.com/in/abhinav-shandilya/" target="_blank">LINKEDIN</a>
        <a href="https://abhinav-shandilya.vercel.app/" target="_blank">PORTFOLIO</a>
    </div>
</div>
""", unsafe_allow_html=True)