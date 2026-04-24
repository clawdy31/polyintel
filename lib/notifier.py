#!/usr/bin/env python3
"""
Telegram notifier — sends alerts for position moves and opportunities
"""
import sys
import os
import time
import json
from datetime import datetime

# Add parent dir to path for config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import config
    HAS_CONFIG = all([
        getattr(config, 'TELEGRAM_BOT_TOKEN', None),
        getattr(config, 'TELEGRAM_CHAT_ID', None),
    ])
except Exception:
    HAS_CONFIG = False

ALERT_STATE_FILE = os.path.join(os.path.dirname(__file__), "..", ".alert_state.json")


def _load_state() -> dict:
    if os.path.exists(ALERT_STATE_FILE):
        try:
            return json.load(open(ALERT_STATE_FILE))
        except Exception:
            pass
    return {"last_alerts": {}, "last_scan": None}


def _save_state(state: dict):
    with open(ALERT_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


async def _send_telegram(message: str, dry_run: bool = False) -> bool:
    if not HAS_CONFIG:
        print("[notifier] Config not loaded — skipping Telegram")
        print(f"[notifier] Message: {message[:200]}")
        return False

    import httpx
    token = getattr(config, 'TELEGRAM_BOT_TOKEN', '')
    chat_id = getattr(config, 'TELEGRAM_CHAT_ID', '')

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    if dry_run:
        print(f"[notifier] DRY RUN: {message[:200]}")
        return True

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if data.get("ok"):
                return True
            print(f"[notifier] Telegram error: {data}")
            return False
    except Exception as e:
        print(f"[notifier] Failed to send Telegram: {e}")
        return False


def format_position_alert(
    market_name: str,
    side: str,
    size: float,
    entry_price: float,
    current_price: float,
    pnl: float,
    url: str = "",
) -> str:
    emoji = "📈" if pnl >= 0 else "📉"
    direction = "⬆️" if current_price > entry_price else "⬇️"
    lines = [
        f"{emoji} *Position Alert*",
        f"_{market_name[:80]}_",
        "",
        f"Direction: {side} {int(size)} shares",
        f"Entry: ${entry_price:.4f}",
        f"Current: ${current_price:.4f} {direction}",
        f"P&L: *${pnl:.2f}*",
    ]
    if url:
        lines.append(f"[View Market]({url})")
    return "\n".join(lines)


def format_opportunity_alert(
    question: str,
    volume: float,
    opportunity_type: str,
    details: dict,
    url: str = "",
) -> str:
    lines = [
        f"🔔 *Opportunity Detected*",
        f"_{question[:80]}_",
        "",
        f"Type: {opportunity_type}",
        f"24h Volume: ${volume:,.0f}",
    ]
    if opportunity_type == "edge":
        lines.append(f"YES: {details.get('yes', 0):.4f} | NO: {details.get('no', 0):.4f}")
        lines.append(f"Sum: {details.get('sum', 0):.4f} — edge available!")
    elif opportunity_type == "price_move":
        lines.append(f"Price moved {details.get('move_pct', 0):.1f}% from last trade")
    if url:
        lines.append(f"[Trade Now]({url})")
    return "\n".join(lines)


def format_portfolio_summary(
    total_value: float,
    total_pnl: float,
    cash: float,
    position_count: int,
) -> str:
    emoji = "📈" if total_pnl >= 0 else "📉"
    return (
        f"📊 *Portfolio Update*\n"
        f"_{datetime.now().strftime('%H:%M %Z')}_\n\n"
        f"Total Value: *${total_value:,.2f}*\n"
        f"{emoji} P&L: *${total_pnl:,.2f}*\n"
        f"Cash: ${cash:,.2f}\n"
        f"Positions: {position_count}"
    )


async def check_and_alert(
    positions: list[dict],
    cash: float,
    min_move_pct: float = 5.0,
    dry_run: bool = False,
) -> list[str]:
    """
    Check positions against alert thresholds and send Telegram alerts.
    Returns list of alerts sent.
    """
    state = _load_state()
    alerts_sent = []

    for pos in positions:
        key = f"{pos.get('asset_id', '')}:{pos.get('side', '')}"
        market = pos.get("market_name", "Unknown")
        side = pos.get("side", "BUY")
        size = float(pos.get("size", 0))
        entry = float(pos.get("price", 0))
        current = float(pos.get("current_price", entry))
        pnl = float(pos.get("pnl", 0))
        url = f"https://polymarket.com/market/{pos.get('slug', '')}"

        if entry == 0:
            continue

        move_pct = abs(current - entry) / entry * 100

        if move_pct >= min_move_pct:
            last_alert = state["last_alerts"].get(key, {})
            last_alert_time = last_alert.get("time", 0)

            # Rate limit: only alert once per hour per position
            if time.time() - last_alert_time > 3600:
                msg = format_position_alert(
                    market, side, size, entry, current, pnl, url
                )
                if await _send_telegram(msg, dry_run=dry_run):
                    state["last_alerts"][key] = {"time": time.time(), "move_pct": move_pct}
                    alerts_sent.append(market)

    _save_state(state)
    return alerts_sent


def send_daily_brief(
    top_opportunities: list[dict],
    portfolio_summary: dict,
    dry_run: bool = False,
) -> bool:
    """Send morning brief to Telegram."""
    if not HAS_CONFIG:
        print("[notifier] Morning brief skipped — no config")
        return False

    import asyncio
    import httpx

    lines = [
        "🌅 *Good Morning Imran!*\n",
        f"_{datetime.now().strftime('%A, %B %d')}_\n",
        "─" * 30,
        f"\n📊 *Portfolio*\n",
        f"Value: ${portfolio_summary.get('total_value', 0):,.2f}",
        f"P&L: ${portfolio_summary.get('total_pnl', 0):,.2f}",
        f"Cash: ${portfolio_summary.get('cash', 0):,.2f}",
        f"Positions: {portfolio_summary.get('position_count', 0)}",
    ]

    if top_opportunities:
        lines.append("\n🔥 *Top Opportunities*\n")
        for o in top_opportunities[:5]:
            lines.append(f"• {o.get('question', 'Unknown')[:60]}")
            lines.append(f"  Vol: ${o.get('volume_24h', 0):,.0f} | YES: {o.get('yes_price', 0):.4f}")

    msg = "\n".join(lines)

    if dry_run:
        print(f"[notifier] Morning brief:\n{msg}")
        return True

    token = getattr(config, 'TELEGRAM_BOT_TOKEN', '')
    chat_id = getattr(config, 'TELEGRAM_CHAT_ID', '')

    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=15,
        )
        return response.json().get("ok", False)
    except Exception as e:
        print(f"[notifier] Morning brief failed: {e}")
        return False


# ─── CLI runner ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio

    async def main():
        from lib.fetcher import get_positions, get_cash_balance, get_clob_balance, build_token_cache, get_markets

        print("[notifier] Running position alert check...")

        try:
            from config import (
                POLY_PRIVATE_KEY, POLY_WALLET, POLY_API_KEY,
                POLY_API_SECRET, POLY_API_PASSPHRASE,
                POLYGON_RPC, ALERT_PRICE_MOVE_PCT,
            )
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds

            creds = ApiCreds(
                api_key=POLY_API_KEY,
                api_secret=POLY_API_SECRET,
                api_passphrase=POLY_API_PASSPHRASE,
            )
            client = ClobClient(
                "https://clob.polymarket.com", chain_id=137,
                key=POLY_PRIVATE_KEY, creds=creds,
                signature_type=0, funder=POLY_WALLET,
            )

            build_token_cache(get_markets(limit=200))
            positions = get_positions(client)
            cash = get_cash_balance(POLY_WALLET, POLYGON_RPC) or 0
            clob_bal = get_clob_balance(client) or 0
            total_cash = cash + clob_bal

            alerts = await check_and_alert(
                positions,
                total_cash,
                min_move_pct=getattr(config, 'ALERT_PRICE_MOVE_PCT', 5.0),
                dry_run=not HAS_CONFIG,
            )

            if alerts:
                print(f"[notifier] Sent alerts for: {', '.join(alerts)}")
            else:
                print("[notifier] No alerts triggered")

        except Exception as e:
            print(f"[notifier] Error: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(main())
