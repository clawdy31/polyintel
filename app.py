#!/usr/bin/env python3
"""
Polymarket Intelligence Dashboard — Streamlit App
Run: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import time
from datetime import datetime, timedelta
import os
import sys

# ─── Config ──────────────────────────────────────────────────────────────────

CONFIG_LOADED = False
try:
    import config
    POLY_PRIVATE_KEY = config.POLY_PRIVATE_KEY
    POLY_WALLET = config.POLY_WALLET
    POLY_API_KEY = config.POLY_API_KEY
    POLY_API_SECRET = config.POLY_API_SECRET
    POLY_API_PASSPHRASE = config.POLY_API_PASSPHRASE
    POLYGON_RPC = getattr(config, 'POLYGON_RPC', 'https://rpc-mainnet.matic.quiknode.pro')
    ALERT_THRESHOLD = getattr(config, 'ALERT_PRICE_MOVE_PCT', 5.0)
    CONFIG_LOADED = True
except Exception:
    POLY_PRIVATE_KEY = os.environ.get("POLY_PRIVATE_KEY", "")
    POLY_WALLET = os.environ.get("POLY_WALLET", "")
    POLY_API_KEY = os.environ.get("POLY_API_KEY", "")
    POLY_API_SECRET = os.environ.get("POLY_API_SECRET", "")
    POLY_API_PASSPHRASE = os.environ.get("POLY_API_PASSPHRASE", "")
    POLYGON_RPC = os.environ.get("POLYGON_RPC", "https://rpc-mainnet.matic.quiknode.pro")
    ALERT_THRESHOLD = 5.0

# ─── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="PolyIntel — Polymarket Dashboard",
    page_icon="📊",
    layout="wide",
    menu_items={
        "About": "## Polymarket Intelligence Dashboard\nBuilt by Clawdy for Imran ⚡",
    },
)

# ─── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
.stApp { background: #0d1117; color: #e6edf3; }
.stMetric { background: #161b22 !important; border: 1px solid #30363d !important; border-radius: 8px; padding: 12px; }
.stMetric label { color: #8b949e !important; }
.stMetric [data-testid="stMetricValue"] { color: #e6edf3 !important; font-size: 1.6rem !important; }
.stTabs [data-baseweb="tab-list"] { background: #161b22; border-radius: 8px; }
.stTabs [data-baseweb="tab"] { color: #8b949e; }
.stTabs [aria-selected="true"] { background: #1f6feb !important; color: white !important; border-radius: 8px; }
div[data-testid="stHorizontalBlock"] > div { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
.stButton > button { background: #1f6feb; color: white; border: none; border-radius: 8px; font-weight: 600; }
.stButton > button:hover { background: #388bfd; }
a { color: #58a6ff; text-decoration: none; }
a:hover { text-decoration: underline; }
.stExpander { background: #161b22; border: 1px solid #30363d; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ─── API clients ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def fetch_markets(limit=200):
    resp = requests.get("https://gamma-api.polymarket.com/markets", params={"limit": limit}, timeout=15)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300)
def fetch_trending(limit=20):
    markets = fetch_markets(limit=limit * 2)
    return sorted(markets, key=lambda m: float(m.get("volume24hr", 0) or 0), reverse=True)[:limit]


@st.cache_data(ttl=120)
def fetch_closing_soon(hours=48):
    markets = fetch_markets(limit=500)
    now = time.time()
    cutoff = now + hours * 3600
    result = []
    for m in markets:
        try:
            end = m.get("endTime", "")
            if end:
                ts = time.mktime(time.strptime(end[:19], "%Y-%m-%dT%H:%M:%S"))
                if now < ts < cutoff:
                    result.append(m)
        except Exception:
            continue
    return sorted(result, key=lambda m: m.get("endTime", ""))[:20]


@st.cache_data(ttl=60)
def fetch_soccer():
    markets = fetch_markets(limit=500)
    keywords = ["football", "soccer", "epl", "premier league", "champions league", "la liga", "bundesliga", "serie a"]
    soccer = []
    for m in markets:
        text = (m.get("question", "") + " " + " ".join(m.get("tags", []) or [])).lower()
        if any(k in text for k in keywords):
            soccer.append(m)
    return soccer[:30]


def get_clob_client():
    if not CONFIG_LOADED or not POLY_PRIVATE_KEY:
        return None
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds
        creds = ApiCreds(api_key=POLY_API_KEY, api_secret=POLY_API_SECRET, api_passphrase=POLY_API_PASSPHRASE)
        return ClobClient(
            "https://clob.polymarket.com", chain_id=137,
            key=POLY_PRIVATE_KEY, creds=creds,
            signature_type=0, funder=POLY_WALLET,
        )
    except Exception as e:
        st.warning(f"CLOB client error: {e}")
        return None


def get_cash_balance():
    if not CONFIG_LOADED:
        return None
    try:
        from web3 import Web3
        USDC = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
        abi = [{"inputs":[{"name":"a","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
        c = w3.eth.contract(address=Web3.to_checksum_address(USDC), abi=abi)
        bal = c.functions.balanceOf(Web3.to_checksum_address(POLY_WALLET)).call()
        return bal / 1e6
    except Exception:
        return None


def get_positions(client):
    try:
        return client.get_trades() or []
    except Exception:
        return []


# ─── Build token name cache ───────────────────────────────────────────────────

_token_cache = {}
_cond_cache = {}

def build_cache(markets):
    for m in markets:
        for tid in m.get("clobTokenIds", []) or []:
            _token_cache[tid] = m.get("question", "Unknown")
        cid = m.get("conditionId", "")
        if cid:
            _cond_cache[cid] = m.get("question", "Unknown")


def lookup_name(asset_id="", condition_id="") -> str:
    if asset_id in _token_cache:
        return _token_cache[asset_id]
    if condition_id in _cond_cache:
        return _cond_cache[condition_id]
    return "Unknown"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def fmt_currency(v):
    return f"${v:,.2f}"


def fmt_pnl(v):
    emoji = "📈" if v >= 0 else "📉"
    return f"{emoji} ${abs(v):,.2f}"


def parse_price(prices, idx=0):
    try:
        return float(prices[idx] or 0)
    except (IndexError, TypeError, ValueError):
        return 0.0


def pct_bar(value, max_val, color_pos="#3fb950", color_neg="#f85149"):
    if max_val == 0:
        return ""
    pct = min(value / max_val, 1.0)
    color = color_pos if value >= 0 else color_neg
    return f"<div style='background:#21262d;border-radius:4px;height:8px;width:100%'><div style='background:{color};border-radius:4px;height:8px;width:{pct*100:.0f}%'></div></div>"


# ─── Main UI ──────────────────────────────────────────────────────────────────

st.title("📊 PolyIntel — Polymarket Intelligence Dashboard")
st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} IST")

if not CONFIG_LOADED:
    st.warning("⚠️ Config not loaded. Copy `config.example.py` to `config.py` and restart for full functionality.")

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Settings")
    st.divider()
    alert_threshold = st.slider("Alert threshold (%)", 1.0, 20.0, ALERT_THRESHOLD, 0.5)
    refresh = st.checkbox("Auto-refresh (60s)", value=False)
    st.divider()
    st.caption("**Credentials**")
    if CONFIG_LOADED:
        st.success("✅ CLOB connected")
        st.caption(f"Wallet: `{POLY_WALLET[:8]}...{POLY_WALLET[-4:]}`")
    else:
        st.error("❌ Not configured")
    st.divider()
    st.caption("**Navigation**")
    page = st.radio("Go to", [
        "📈 Portfolio",
        "🔥 Trending",
        "⚽ Football",
        "🔍 Market Scanner",
        "⏰ Closing Soon",
    ], label_visibility="collapsed")

# ─── Portfolio Page ───────────────────────────────────────────────────────────

if page == "📈 Portfolio":
    st.header("Your Portfolio")

    client = get_clob_client()
    cash = get_cash_balance()
    clob_bal = None

    if client:
        try:
            from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
            result = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
            clob_bal = int(result.get("balance", 0)) / 1e6
        except Exception:
            pass

    total_cash = (cash or 0) + (clob_bal or 0)
    markets = fetch_markets(limit=200)
    build_cache(markets)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("💵 Cash (EOA)", fmt_currency(cash or 0))
    with col2:
        st.metric("🏦 CLOB Balance", fmt_currency(clob_bal or 0))
    with col3:
        st.metric("💰 Total Cash", fmt_currency(total_cash))
    with col4:
        st.metric("📊 Markets Loaded", f"{len(markets)}")

    if client:
        positions = get_positions(client)
        trades = get_positions(client)

        if trades:
            st.subheader("🏆 Your Positions")
            rows = []
            for t in trades:
                asset_id = t.get("asset_id", "")
                condition_id = t.get("market", "")
                name = lookup_name(asset_id, condition_id)
                size = float(t.get("size", 0))
                price = float(t.get("price", 0))
                side = t.get("side", "BUY")

                # Find current price
                mkt = next((m for m in markets if asset_id in (m.get("clobTokenIds", []) or [])), None)
                current_price = parse_price(mkt.get("outcomePrices", []) if mkt else [], 0)
                if current_price == 0 and mkt:
                    prices = mkt.get("outcomePrices", [])
                    if len(prices) >= 2:
                        current_price = float(prices[0])

                pnl = (current_price - price) * size if side == "BUY" else (price - current_price) * size
                pnl_pct = ((current_price - price) / price * 100) if price > 0 else 0
                slug = mkt.get("slug", "") if mkt else ""
                url = f"https://polymarket.com/market/{slug}" if slug else ""

                rows.append({
                    "Market": f"[{name[:50]}]({url})" if url else name[:50],
                    "Side": side,
                    "Size": int(size),
                    "Entry": f"${price:.4f}",
                    "Current": f"${current_price:.4f}",
                    "P&L": fmt_pnl(pnl),
                    "P&L %": f"{pnl_pct:+.1f}%",
                })

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # P&L chart
            pnl_vals = []
            labels = []
            for r in rows:
                try:
                    pnl_str = r["P&L"].replace("📈 ", "").replace("📉 ", "").replace("$", "").replace(",", "")
                    pnl_vals.append(float(pnl_str))
                    labels.append(r["Market"][:30])
                except Exception:
                    pass

            if pnl_vals:
                fig = go.Figure(go.Bar(
                    x=labels,
                    y=pnl_vals,
                    marker_color=["#3fb950" if v >= 0 else "#f85149" for v in pnl_vals],
                ))
                fig.update_layout(
                    title="Position P&L",
                    paper_bgcolor="#0d1117",
                    plot_bgcolor="#0d1117",
                    font_color="#e6edf3",
                    height=300,
                    margin=dict(l=20, r=20, t=40, b=20),
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No positions found. Start trading to see your portfolio here!")
    else:
        st.warning("Configure `config.py` to see your live positions.")

    # Trending markets quick view
    st.subheader("🔥 Trending Markets")
    trending = fetch_trending(10)
    t_data = []
    for m in trending:
        prices = m.get("outcomePrices", [])
        yes_price = parse_price(prices, 0)
        vol = float(m.get("volume24hr", 0) or 0)
        slug = m.get("slug", "")
        t_data.append({
            "Market": m.get("question", "Unknown")[:60],
            "YES Price": f"${yes_price:.4f}",
            "24h Volume": f"${vol:,.0f}",
            "Link": f"[Trade](https://polymarket.com/market/{slug})" if slug else "",
        })
    st.dataframe(pd.DataFrame(t_data), use_container_width=True, hide_index=True)


# ─── Trending Page ────────────────────────────────────────────────────────────

elif page == "🔥 Trending":
    st.header("🔥 Trending Markets (24h Volume)")
    trending = fetch_trending(30)

    t_data = []
    for m in trending:
        prices = m.get("outcomePrices", [])
        yes_price = parse_price(prices, 0)
        no_price = parse_price(prices, 1) if len(prices) > 1 else (1 - yes_price)
        vol = float(m.get("volume24hr", 0) or 0)
        slug = m.get("slug", "")
        t_data.append({
            "Market": m.get("question", "Unknown"),
            "YES": f"${yes_price:.4f}",
            "NO": f"${no_price:.4f}",
            "Spread": f"${abs(yes_price - no_price):.4f}",
            "24h Volume": f"${vol:,.0f}",
            "Category": ", ".join(m.get("tags", []) or []),
            "Link": slug,
        })

    df = pd.DataFrame(t_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Volume chart
    fig = px.bar(
        df.head(15),
        x="Market",
        y=[float(v.replace("$","").replace(",","")) for v in df.head(15)["24h Volume"]],
        title="Top 15 by 24h Volume",
        labels={"y": "Volume (USD)"},
        color_discrete_sequence=["#1f6feb"],
    )
    fig.update_layout(
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font_color="#e6edf3",
        height=400,
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Football Page ────────────────────────────────────────────────────────────

elif page == "⚽ Football":
    st.header("⚽ Football Markets")
    soccer = fetch_soccer()

    if not soccer:
        st.warning("No soccer markets found right now. Check back later!")
    else:
        cols = st.columns(2)
        for idx, m in enumerate(soccer[:20]):
            prices = m.get("outcomePrices", [])
            yes_price = parse_price(prices, 0)
            no_price = parse_price(prices, 1) if len(prices) > 1 else (1 - yes_price)
            vol = float(m.get("volume24hr", 0) or 0)
            slug = m.get("slug", "")
            end_time = m.get("endTime", "Unknown")
            try:
                end_fmt = datetime.strptime(end_time[:19], "%Y-%m-%dT%H:%M:%S").strftime("%b %d, %H:%M")
            except Exception:
                end_fmt = end_time

            with cols[idx % 2]:
                st.markdown(f"""
                <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:12px">
                    <div style="font-weight:600;font-size:0.95rem;margin-bottom:8px">{m.get('question','Unknown')[:80]}</div>
                    <div style="display:flex;gap:16px;align-items:center">
                        <div>
                            <div style="color:#8b949e;font-size:0.75rem">YES</div>
                            <div style="font-size:1.3rem;font-weight:700;color:#3fb950">${yes_price:.4f}</div>
                        </div>
                        <div>
                            <div style="color:#8b949e;font-size:0.75rem">NO</div>
                            <div style="font-size:1.3rem;font-weight:700;color:#f85149">${no_price:.4f}</div>
                        </div>
                        <div>
                            <div style="color:#8b949e;font-size:0.75rem">Vol</div>
                            <div style="font-size:0.9rem">${vol:,.0f}</div>
                        </div>
                    </div>
                    <div style="color:#8b949e;font-size:0.8rem;margin-top:8px">⏰ {end_fmt}</div>
                    <a href="https://polymarket.com/market/{slug}" target="_blank" style="color:#58a6ff;font-size:0.85rem">Trade →</a>
                </div>
                """, unsafe_allow_html=True)


# ─── Market Scanner ───────────────────────────────────────────────────────────

elif page == "🔍 Market Scanner":
    st.header("🔍 Market Scanner")
    st.caption("Finds edge opportunities and significant price movements")

    col1, col2 = st.columns([1, 2])

    with col1:
        min_volume = st.number_input("Min 24h Volume ($)", 100, 100000, 5000, 500)
        threshold = st.slider("Alert threshold (%)", 1.0, 20.0, 5.0, 0.5)
        scan_btn = st.button("🔄 Scan Markets")

    markets = fetch_markets(limit=300)
    build_cache(markets)

    opportunities = []
    for m in markets:
        vol = float(m.get("volume24hr", 0) or 0)
        if vol < min_volume:
            continue
        prices = m.get("outcomePrices", [])
        if len(prices) < 2:
            continue
        try:
            yes_p = float(prices[0] or 0)
            no_p = float(prices[1] or 0)
            total = yes_p + no_p
            last = float(m.get("lastTradePrice", 0) or yes_p)

            if total < 0.96:
                opportunities.append({
                    "Type": "⚡ Edge",
                    "Market": m.get("question", "Unknown"),
                    "YES": f"${yes_p:.4f}",
                    "NO": f"${no_p:.4f}",
                    "Sum": f"${total:.4f}",
                    "24h Vol": f"${vol:,.0f}",
                    "Slug": m.get("slug", ""),
                })
            elif last > 0.01 and abs(yes_p - last) / last * 100 > threshold:
                opportunities.append({
                    "Type": "📍 Price Move",
                    "Market": m.get("question", "Unknown"),
                    "YES": f"${yes_p:.4f}",
                    "Last": f"${last:.4f}",
                    "Move": f"{abs(yes_p - last) / last * 100:+.1f}%",
                    "24h Vol": f"${vol:,.0f}",
                    "Slug": m.get("slug", ""),
                })
        except Exception:
            continue

    if opportunities:
        df = pd.DataFrame(opportunities)
        st.dataframe(df.drop(columns=["Slug"] if "Slug" in df.columns else []), use_container_width=True, hide_index=True)
    else:
        st.success("No opportunities found at current thresholds. Try lowering the volume filter or raising the threshold.")


# ─── Closing Soon ──────────────────────────────────────────────────────────────

elif page == "⏰ Closing Soon":
    st.header("⏰ Closing Soon")
    hours = st.slider("Markets closing within (hours)", 1, 72, 24)
    closing = fetch_closing_soon(hours=hours)

    if closing:
        rows = []
        for m in closing:
            prices = m.get("outcomePrices", [])
            yes_price = parse_price(prices, 0)
            vol = float(m.get("volume24hr", 0) or 0)
            end = m.get("endTime", "Unknown")
            try:
                end_fmt = datetime.strptime(end[:19], "%Y-%m-%dT%H:%M:%S").strftime("%b %d, %H:%M %Z")
            except Exception:
                end_fmt = end
            slug = m.get("slug", "")
            rows.append({
                "Market": m.get("question", "Unknown"),
                "YES": f"${yes_price:.4f}",
                "24h Volume": f"${vol:,.0f}",
                "Closes": end_fmt,
                "Link": slug,
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info(f"No markets closing within {hours} hours.")

# ─── Auto refresh ──────────────────────────────────────────────────────────────

if refresh:
    time.sleep(60)
    st.rerun()
