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
    page_title="NIFTY IT Research",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

TICKERS = ["INFY.NS", "TECHM.NS", "WIPRO.NS", "HCLTECH.NS"]
SECTOR_LABEL = "IT services"

# Map ticker -> a human display name (edit as needed)
TICKER_NAMES = {
    "INFY.NS": "Infosys",
    "TECHM.NS": "Tech Mahindra",
    "WIPRO.NS": "Wipro",
    "HCLTECH.NS": "HCLTech",
}

POSITIVE = "#1D9E75"
NEGATIVE = "#E24B4A"
ACCENT = "#378ADD"
MUTED = "#888780"
BENCHMARK = "#D4537E"

# ----------------------------------------------------------------------------
# DB CONNECTION
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
    query = text(
        """
        SELECT date, close_price as close, rolling_7d_avg, data_status
        FROM analytics_summary
        WHERE ticker = :ticker
        ORDER BY date DESC
        LIMIT :days
        """
    )
    df = pd.read_sql(query, engine, params={"ticker": ticker, "days": days})
    return df.sort_values("date").reset_index(drop=True)

@st.cache_data(ttl=300)
def load_latest_metrics(ticker: str) -> pd.Series:
    query = text(
        """
        SELECT close_price as close, rolling_7d_avg, net_profit_margin_pct, pe_ratio, date, data_status
        FROM analytics_summary
        WHERE ticker = :ticker
        ORDER BY date DESC
        LIMIT 1
        """
    )
    df = pd.read_sql(query, engine, params={"ticker": ticker})
    return df.iloc[0] if not df.empty else pd.Series(dtype="float64")

@st.cache_data(ttl=300)
def load_sector_index(days: int = 30) -> pd.DataFrame:
    """Average close price across all tracked tickers, per day, as a sector benchmark line."""
    query = text(
        """
        SELECT date, AVG(close_price) AS sector_avg_close
        FROM analytics_summary
        WHERE ticker = ANY(:tickers)
        GROUP BY date
        ORDER BY date DESC
        LIMIT :days
        """
    )
    df = pd.read_sql(query, engine, params={"tickers": TICKERS, "days": days})
    return df.sort_values("date").reset_index(drop=True)

@st.cache_data(ttl=300)
def load_sector_avg_pe() -> float:
    query = text(
        """
        SELECT AVG(pe_ratio) AS avg_pe
        FROM (
            SELECT DISTINCT ON (ticker) ticker, pe_ratio
            FROM analytics_summary
            WHERE ticker = ANY(:tickers)
            ORDER BY ticker, date DESC
        ) latest
        """
    )
    df = pd.read_sql(query, engine, params={"tickers": TICKERS})
    return float(df["avg_pe"].iloc[0]) if not df.empty else float("nan")

@st.cache_data(ttl=60)
def load_pipeline_status() -> pd.Series:
    query = text(
        """
        SELECT execution_time, status
        FROM pipeline_logs
        ORDER BY run_id DESC
        LIMIT 1
        """
    )
    df = pd.read_sql(query, engine)
    return df.iloc[0] if not df.empty else pd.Series(dtype="object")

# ----------------------------------------------------------------------------
# STYLING
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e1117;
    }
    section[data-testid="stSidebar"] {
        background-color: #12151c;
    }
    div[data-baseweb="select"] > div {
        background-color: #161a23 !important;
        border-color: #2a2f3a !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="select"] > div:hover {
        border-color: #378ADD !important;
    }
    .kpi-card {
        background-color: #161a23;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        border: 1px solid #232733;
    }
    .kpi-label {
        font-size: 12px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: #8b8f9c;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 26px;
        font-weight: 600;
        color: #e8eaed;
    }
    .badge {
        display: inline-block;
        font-size: 11px;
        padding: 2px 10px;
        border-radius: 999px;
        margin-left: 8px;
        vertical-align: middle;
    }
    .badge-nse {
        background: rgba(55, 138, 221, 0.15);
        color: #6fb3ff;
    }
    .badge-sector {
        background: #1e2230;
        color: #8b8f9c;
        border: 1px solid #2a2f3a;
    }
    .badge-pe {
        background: #1e2230;
        color: #8b8f9c;
        border-radius: 6px;
        font-size: 11px;
        padding: 2px 8px;
    }
    .status-dot {
        height: 8px;
        width: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
    }
    .footer {
        border-top: 1px solid #232733;
        margin-top: 2rem;
        padding-top: 0.75rem;
        font-size: 11px;
        color: #6b6f7a;
        display: flex;
        justify-content: space-between;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# SIDEBAR
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("**Prepared by: Abhinav Shandilya**")

    pipeline = load_pipeline_status()
    if not pipeline.empty:
        run_time = pd.to_datetime(pipeline["execution_time"])
        age_minutes = (datetime.now(timezone.utc) - run_time.tz_localize("UTC")).total_seconds() / 60 \
            if run_time.tzinfo is None else (datetime.now(timezone.utc) - run_time).total_seconds() / 60
        is_fresh = age_minutes < 24 * 60
        dot_color = "#1D9E75" if is_fresh else "#E24B4A" if age_minutes > 48 * 60 else "#EF9F27"
        relative = f"{int(age_minutes)} min ago" if age_minutes < 60 else f"{int(age_minutes // 60)} hr ago"
        st.markdown(
            f'<span class="status-dot" style="background:{dot_color};"></span>'
            f'<span style="font-size:13px; color:#c7cad1;">Synced {relative}</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="status-dot" style="background:#E24B4A;"></span>'
            '<span style="font-size:13px; color:#c7cad1;">No pipeline runs found</span>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("**📋 Select company**")
    selected_ticker = st.selectbox("Company", TICKERS, index=TICKERS.index("HCLTECH.NS"))

# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
company_name = TICKER_NAMES.get(selected_ticker, selected_ticker)

st.markdown(
    f"""
    <div style="display:flex; align-items:center; margin-bottom: 1.25rem;">
        <span style="font-size:28px; font-weight:700; color:#e8eaed;">
            📈 {selected_ticker} · {company_name}
        </span>
        <span class="badge badge-nse">NSE</span>
        <span class="badge badge-sector">{SECTOR_LABEL}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

latest = load_latest_metrics(selected_ticker)
history = load_price_history(selected_ticker, days=30)

if latest.empty or history.empty:
    st.warning(
        f"No recent data found for {selected_ticker}. The pipeline may not have run yet — "
        "check `pipeline_logs` or re-run `ingest.py` / `transform.py`."
    )
else:
    # ---- V2 Data Quality UI Alerts ----
    status = latest.get('data_status', 'ACTUAL')
    if status == 'IMPUTED_API_OUTAGE':
        st.error("⚠️ **WARNING:** Today's price data is imputed due to an API outage. The values shown are carried forward from the previous trading day.")
    elif status == 'MARKET_HALT':
        st.warning("⏸️ **NOTICE:** Today's volume is zero. The stock may be halted or it is a non-trading day.")

    # ---- Day-over-day deltas ----
    if len(history) >= 2:
        prev_close = history["close"].iloc[-2]
        latest_close = history["close"].iloc[-1]
        close_delta_pct = ((latest_close - prev_close) / prev_close) * 100
    else:
        close_delta_pct = 0.0

    sector_avg_pe = load_sector_avg_pe()

    # ---- KPI ROW ----
    col1, col2, col3 = st.columns(3)

    with col1:
        with st.container():
            st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
            st.markdown('<div class="kpi-label">Latest close price</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="kpi-value">₹{latest["close"]:.2f}</div>', unsafe_allow_html=True)
            arrow = "▲" if close_delta_pct >= 0 else "▼"
            color = POSITIVE if close_delta_pct >= 0 else NEGATIVE
            st.markdown(
                f'<span style="color:{color}; font-size:13px;">{arrow} {abs(close_delta_pct):.2f}%</span>',
                unsafe_allow_html=True,
            )
            spark = go.Figure(
                go.Scatter(
                    y=history["close"].tail(7),
                    mode="lines",
                    line=dict(width=2, color=color),
                    fill="tozeroy",
                    fillcolor=f"rgba({29 if close_delta_pct>=0 else 226},{158 if close_delta_pct>=0 else 74},{117 if close_delta_pct>=0 else 74},0.10)",
                )
            )
            spark.update_layout(
                margin=dict(l=0, r=0, t=4, b=0),
                height=40,
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(
                spark,
                config={"staticPlot": True, "displayModeBar": False},
                use_container_width=True,
                key=f"spark_close_{selected_ticker}",
            )
            st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        with st.container():
            st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
            st.markdown('<div class="kpi-label">P/E ratio</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="kpi-value">{latest["pe_ratio"]:.2f}</div>', unsafe_allow_html=True)
            if not pd.isna(sector_avg_pe):
                st.markdown(
                    f'<span class="badge-pe">Sector avg {sector_avg_pe:.1f}</span>',
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

    with col3:
        with st.container():
            st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
            st.markdown('<div class="kpi-label">Net profit margin</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="kpi-value">{latest["net_profit_margin_pct"]:.2f}%</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- MAIN PRICE CHART ----
    st.markdown("#### 📉 Price trend vs 7-day rolling average")

    sector_index = load_sector_index(days=30)

    y_min = min(history["close"].min(), history["rolling_7d_avg"].min()) * 0.97
    y_max = max(history["close"].max(), history["rolling_7d_avg"].max()) * 1.03

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=history["date"],
            y=history["close"],
            mode="lines",
            name="Close price",
            line=dict(color=ACCENT, width=2.5),
            fill="tozeroy",
            fillcolor="rgba(55, 138, 221, 0.08)",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=history["date"],
            y=history["rolling_7d_avg"],
            mode="lines",
            name="7-day avg",
            line=dict(color=MUTED, width=1.5, dash="dash"),
        )
    )

    if not sector_index.empty:
        fig.add_trace(
            go.Scatter(
                x=sector_index["date"],
                y=sector_index["sector_avg_close"],
                mode="lines",
                name="Sector index",
                line=dict(color=BENCHMARK, width=1.5, dash="dot"),
                opacity=0.7,
            )
        )

    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c7cad1"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=False, color="#8b8f9c"),
        yaxis=dict(
            range=[y_min, y_max],
            showgrid=True,
            gridcolor="rgba(255,255,255,0.05)",
            color="#8b8f9c",
        ),
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ----------------------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------------------
st.markdown(
    """
    <div class="footer">
        <span>Data: Yahoo Finance · refreshed nightly via automated pipeline</span>
        <a href="https://github.com/" target="_blank" style="color:#6b6f7a; text-decoration:none;">
            🔗 View repo
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)
