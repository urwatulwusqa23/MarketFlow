"""MarketFlow — Streamlit dashboard."""
import os
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import psycopg2
import streamlit as st
from dotenv import load_dotenv
from plotly.subplots import make_subplots
from sqlalchemy import create_engine, text

load_dotenv()

st.set_page_config(
    page_title="MarketFlow",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

COLORS = {
    "price":      "#4f8ef7",
    "sma20":      "#ffd32a",
    "sma50":      "#ff6b81",
    "up":         "#00d26a",
    "down":       "#ff4757",
    "volume":     "#4f8ef7",
    "avg":        "#ffd32a",
    "range_line": "#ff6b81",
}
TMPL = "plotly_dark"
PALETTE = ["#4f8ef7", "#00d26a", "#ffd32a", "#ff6b81", "#a29bfe", "#fd79a8", "#00cec9", "#e17055"]

# ── DB helpers ─────────────────────────────────────────────────────────────────

@st.cache_resource
def _engine():
    u    = os.getenv("POSTGRES_USER",     "marketflow_user")
    pw   = os.getenv("POSTGRES_PASSWORD", "marketflow_pass")
    h    = os.getenv("POSTGRES_HOST",     "localhost")
    port = os.getenv("POSTGRES_PORT",     "5432")
    db   = os.getenv("POSTGRES_DB",       "marketflow")
    return create_engine(f"postgresql+psycopg2://{u}:{pw}@{h}:{port}/{db}")


@st.cache_data(ttl=300)
def q(sql: str, params: dict | None = None) -> pd.DataFrame:
    with _engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def _psycopg2_conn():
    return psycopg2.connect(
        dbname   = os.getenv("POSTGRES_DB",       "marketflow"),
        user     = os.getenv("POSTGRES_USER",     "marketflow_user"),
        password = os.getenv("POSTGRES_PASSWORD", "marketflow_pass"),
        host     = os.getenv("POSTGRES_HOST",     "localhost"),
        port     = os.getenv("POSTGRES_PORT",     "5432"),
    )


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📈 MarketFlow")
    st.caption("Stock ETL Dashboard")
    st.divider()

    try:
        companies = q("SELECT symbol, company_name, sector FROM warehouse.dim_company ORDER BY symbol")
    except Exception as e:
        st.error(f"Cannot connect to database:\n\n{e}")
        st.stop()

    sym_list = companies["symbol"].tolist()
    name_map = dict(zip(companies["symbol"], companies["company_name"]))

    symbol = st.selectbox(
        "Symbol",
        sym_list,
        format_func=lambda s: f"{s}  —  {name_map[s]}",
    )

    bounds = q(
        "SELECT MIN(full_date)::date AS lo, MAX(full_date)::date AS hi "
        "FROM warehouse.v_daily_returns"
    )
    lo = bounds["lo"].iloc[0]
    hi = bounds["hi"].iloc[0]

    c1, c2 = st.columns(2)
    start = c1.date_input("From", value=max(lo, hi - timedelta(days=90)), min_value=lo, max_value=hi)
    end   = c2.date_input("To",   value=hi, min_value=lo, max_value=hi)

    st.divider()

    if st.button("🔄  Run Pipeline", use_container_width=True, type="primary"):
        with st.spinner("Fetching latest prices from Alpha Vantage…"):
            try:
                from src.orchestrate import run as _run  # noqa: PLC0415
                res = _run()
                new_rec  = res["extract"]["records_loaded"]
                new_fact = res["transform"]["facts"]
                st.success(f"✅  {new_rec} new records  ·  {new_fact} facts loaded")
                st.cache_data.clear()
            except SystemExit as ex:
                if ex.code != 0:
                    st.warning("Pipeline finished — check **Data Quality** tab for failures.")
                    st.cache_data.clear()
            except Exception as ex:
                st.error(str(ex))

    st.divider()
    st.caption("Source: Alpha Vantage free tier  \nCache refreshes every 5 min")


# ── Load data ─────────────────────────────────────────────────────────────────

ret = q(
    "SELECT full_date, close_price, daily_return_pct, rolling_5d_return_avg "
    "FROM warehouse.v_daily_returns "
    "WHERE symbol = :sym AND full_date BETWEEN :s AND :e ORDER BY full_date",
    {"sym": symbol, "s": start, "e": end},
)

ma = q(
    "SELECT full_date, close_price, sma_20, sma_50, price_vs_sma20 "
    "FROM warehouse.v_moving_averages "
    "WHERE symbol = :sym AND full_date BETWEEN :s AND :e ORDER BY full_date",
    {"sym": symbol, "s": start, "e": end},
)

vol = q(
    "SELECT full_date, volume, avg_volume_30d, volume_vs_avg_pct, intraday_range_pct "
    "FROM warehouse.v_volume_analysis "
    "WHERE symbol = :sym AND full_date BETWEEN :s AND :e ORDER BY full_date",
    {"sym": symbol, "s": start, "e": end},
)

all_close = q(
    "SELECT symbol, full_date, close_price "
    "FROM warehouse.v_daily_returns "
    "WHERE full_date BETWEEN :s AND :e ORDER BY symbol, full_date",
    {"s": start, "e": end},
)


# ── Header + KPI row ──────────────────────────────────────────────────────────

co = companies[companies["symbol"] == symbol].iloc[0]
st.markdown(
    f"### {symbol} &nbsp;"
    f"<span style='font-size:0.85rem;color:grey'>"
    f"{co['company_name']} · {co['sector']}</span>",
    unsafe_allow_html=True,
)

if not ret.empty:
    lr = ret.iloc[-1]
    lv = vol.iloc[-1] if not vol.empty else None
    lm = ma.iloc[-1]  if not ma.empty  else None

    k1, k2, k3, k4 = st.columns(4)

    day_ret = lr["daily_return_pct"]
    k1.metric(
        "Last Close",
        f"${float(lr['close_price']):,.2f}",
        f"{float(day_ret):+.2f}%  today" if day_ret is not None else None,
    )

    roll = lr["rolling_5d_return_avg"]
    k2.metric(
        "5-Day Avg Return",
        f"{float(roll):+.2f}%" if roll is not None else "—",
    )

    if lv is not None:
        k3.metric(
            "Volume",
            f"{int(lv['volume']):,}",
            f"{float(lv['volume_vs_avg_pct']):+.1f}% vs 30-day avg",
        )
    else:
        k3.metric("Volume", "—")

    if lm is not None:
        vs = float(lm["price_vs_sma20"])
        k4.metric(
            "vs SMA-20",
            f"{vs:+.2f}",
            "above avg" if vs >= 0 else "below avg",
            delta_color="normal" if vs >= 0 else "inverse",
        )
    else:
        k4.metric("vs SMA-20", "—")

st.divider()


# ── Tabs ──────────────────────────────────────────────────────────────────────

t1, t2, t3, t4, t5 = st.tabs([
    "📉  Price & Returns",
    "〰️  Moving Averages",
    "📊  Volume",
    "🔀  Compare All",
    "✅  Data Quality",
])

# ── Tab 1 : Price & Returns ───────────────────────────────────────────────────
with t1:
    if ret.empty:
        st.info("No data in the selected date range.")
    else:
        # Close price area chart
        fig = go.Figure(go.Scatter(
            x=ret["full_date"], y=ret["close_price"].astype(float),
            line=dict(color=COLORS["price"], width=2),
            fill="tozeroy", fillcolor="rgba(79,142,247,0.07)",
            name="Close Price",
        ))
        fig.update_layout(
            title=f"{symbol} — Close Price",
            xaxis_title="Date", yaxis_title="Price (USD)",
            template=TMPL, height=340,
            margin=dict(l=0, r=0, t=44, b=0),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Daily returns bar + rolling avg
        bar_colors = [
            COLORS["up"] if (v or 0) >= 0 else COLORS["down"]
            for v in ret["daily_return_pct"].fillna(0)
        ]
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=ret["full_date"], y=ret["daily_return_pct"].astype(float),
            marker_color=bar_colors, name="Daily Return %",
        ))
        fig2.add_trace(go.Scatter(
            x=ret["full_date"], y=ret["rolling_5d_return_avg"].astype(float),
            line=dict(color=COLORS["sma20"], width=2), name="5-Day Avg",
        ))
        fig2.add_hline(y=0, line_color="grey", line_width=0.6)
        fig2.update_layout(
            title="Daily Return % with 5-Day Rolling Average",
            xaxis_title="Date", yaxis_title="Return %",
            template=TMPL, height=300,
            margin=dict(l=0, r=0, t=44, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig2, use_container_width=True)

        with st.expander("📋  Raw data table"):
            st.dataframe(
                ret.sort_values("full_date", ascending=False).reset_index(drop=True),
                use_container_width=True,
            )

# ── Tab 2 : Moving Averages ───────────────────────────────────────────────────
with t2:
    if ma.empty:
        st.info("No data in the selected date range.")
    else:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=ma["full_date"], y=ma["close_price"].astype(float),
            line=dict(color=COLORS["price"], width=2), name="Close Price",
        ))
        fig3.add_trace(go.Scatter(
            x=ma["full_date"], y=ma["sma_20"].astype(float),
            line=dict(color=COLORS["sma20"], width=1.5, dash="dot"), name="SMA-20",
        ))
        fig3.add_trace(go.Scatter(
            x=ma["full_date"], y=ma["sma_50"].astype(float),
            line=dict(color=COLORS["sma50"], width=1.5, dash="dash"), name="SMA-50",
        ))
        fig3.update_layout(
            title=f"{symbol} — Price vs SMA-20 & SMA-50",
            xaxis_title="Date", yaxis_title="Price (USD)",
            template=TMPL, height=440,
            margin=dict(l=0, r=0, t=44, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig3, use_container_width=True)

        st.info(
            "**How to read this:**  "
            "When the price is above SMA-20 the stock is in a short-term uptrend.  "
            "When SMA-20 crosses above SMA-50 that is called a *golden cross* — a classic bullish signal."
        )

        with st.expander("📋  Raw data table"):
            st.dataframe(
                ma.sort_values("full_date", ascending=False).reset_index(drop=True),
                use_container_width=True,
            )

# ── Tab 3 : Volume ────────────────────────────────────────────────────────────
with t3:
    if vol.empty:
        st.info("No data in the selected date range.")
    else:
        vol_colors = [
            COLORS["up"] if v >= 100 else COLORS["volume"]
            for v in vol["volume_vs_avg_pct"].fillna(100)
        ]
        fig4 = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            row_heights=[0.65, 0.35], vertical_spacing=0.08,
            subplot_titles=("Volume vs 30-Day Average", "Intraday Price Range %"),
        )
        fig4.add_trace(go.Bar(
            x=vol["full_date"], y=vol["volume"].astype(float),
            marker_color=vol_colors, name="Volume",
        ), row=1, col=1)
        fig4.add_trace(go.Scatter(
            x=vol["full_date"], y=vol["avg_volume_30d"].astype(float),
            line=dict(color=COLORS["avg"], width=2), name="30-Day Avg",
        ), row=1, col=1)
        fig4.add_trace(go.Scatter(
            x=vol["full_date"], y=vol["intraday_range_pct"].astype(float),
            fill="tozeroy", fillcolor="rgba(255,107,129,0.12)",
            line=dict(color=COLORS["range_line"], width=1.5), name="Range %",
        ), row=2, col=1)
        fig4.update_layout(
            template=TMPL, height=520,
            margin=dict(l=0, r=0, t=44, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig4, use_container_width=True)
        st.info(
            "🟢 **Green bars** = volume above 30-day average (unusual activity).  "
            "🔵 **Blue bars** = below average — quiet trading day.  "
            "Bottom panel shows the high-low range as % of close price — a proxy for daily volatility."
        )

# ── Tab 4 : Compare All Stocks ────────────────────────────────────────────────
with t4:
    if all_close.empty:
        st.info("No data in the selected date range.")
    else:
        piv  = all_close.pivot(index="full_date", columns="symbol", values="close_price").astype(float)
        norm = piv.div(piv.iloc[0]) * 100   # index to 100 at period start

        fig5 = go.Figure()
        for i, col in enumerate(norm.columns):
            fig5.add_trace(go.Scatter(
                x=norm.index, y=norm[col],
                name=col, line=dict(width=2, color=PALETTE[i % len(PALETTE)]),
            ))
        fig5.add_hline(y=100, line_color="grey", line_dash="dot", line_width=0.8,
                       annotation_text="Breakeven", annotation_position="bottom right")
        fig5.update_layout(
            title=f"Normalized Performance — 100 = closing price on {start}",
            xaxis_title="Date", yaxis_title="Indexed Return",
            template=TMPL, height=460,
            margin=dict(l=0, r=0, t=44, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig5, use_container_width=True)

        st.subheader("Latest Trading Day — All Stocks")
        latest_all = q(
            "SELECT symbol, full_date, close_price, daily_return_pct, rolling_5d_return_avg "
            "FROM warehouse.v_daily_returns "
            "WHERE full_date = (SELECT MAX(full_date) FROM warehouse.v_daily_returns) "
            "ORDER BY daily_return_pct DESC NULLS LAST"
        )
        st.dataframe(
            latest_all.rename(columns={
                "symbol":               "Symbol",
                "full_date":            "Date",
                "close_price":          "Close ($)",
                "daily_return_pct":     "Return %",
                "rolling_5d_return_avg":"5-Day Avg %",
            }),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Close ($)":   st.column_config.NumberColumn(format="$%.2f"),
                "Return %":    st.column_config.NumberColumn(format="%.2f%%"),
                "5-Day Avg %": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )

# ── Tab 5 : Data Quality ──────────────────────────────────────────────────────
with t5:
    try:
        from src.quality_checks import run_quality_checks  # noqa: PLC0415
        conn = _psycopg2_conn()
        try:
            qc = run_quality_checks(conn)
        finally:
            conn.close()

        n_pass  = len(qc["passed"])
        n_total = qc["total"]

        score_col, _ = st.columns([1, 3])
        with score_col:
            st.metric(
                "QC Score",
                f"{n_pass} / {n_total}",
                "All checks passing ✅" if n_pass == n_total else f"{n_total - n_pass} check(s) failing ❌",
                delta_color="normal" if n_pass == n_total else "inverse",
            )

        rows = []
        for r in sorted(qc["passed"] + qc["failed"], key=lambda x: x["name"]):
            rows.append({
                "":       "✅" if r["passed"] else "❌",
                "Check":  r["name"],
                "Value":  r["value"],
                "Rule":   r["message"],
            })

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "":      st.column_config.TextColumn(width="small"),
                "Value": st.column_config.NumberColumn(format="%.2f"),
            },
        )
    except Exception as ex:
        st.error(f"Could not run quality checks: {ex}")
