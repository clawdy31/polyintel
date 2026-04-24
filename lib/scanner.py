#!/usr/bin/env python3
"""
Market opportunity scanner — finds underpriced, high-volume, closing-soon markets
"""
import time
from lib.fetcher import (
    get_markets, get_trending, get_sports_markets,
    get_crypto_markets, get_closing_soon, build_token_cache,
)


CATEGORIES = {
    "⚽ Football": "Soccer",
    "🏀 Basketball": "Basketball",
    "🏈 American Football": "American Football",
    "🎾 Tennis": "Tennis",
    "🏎 F1/Motorsport": "F1",
    "🎮 Esports": "Esports",
    "🎬 Entertainment": "Entertainment",
    "💰 Crypto": "Crypto",
    "🏛 Politics": "Politics",
    "🌍 World": "World",
}


def get_smart_alerts(threshold_pct: float = 5.0) -> dict:
    """Scan for markets with big recent price moves or opportunities."""
    opportunities = []
    markets = get_markets(limit=200)

    for m in markets:
        vol = float(m.get("volume24hr", 0) or 0)
        if vol < 1000:
            continue

        question = m.get("question", "Unknown")
        prices = m.get("outcomePrices", [])
        if not prices or len(prices) < 2:
            continue

        try:
            yes_price = float(prices[0])
            no_price = float(prices[1]) if len(prices) > 1 else (1 - yes_price)
            spread = abs(yes_price - no_price)
            total_prob = yes_price + no_price

            # Flag if YES+NO doesn't sum to ~1 (edge opportunity)
            if total_prob < 0.95:
                opportunities.append({
                    "type": "edge",
                    "market": question,
                    "slug": m.get("slug", ""),
                    "yes": yes_price,
                    "no": no_price,
                    "sum": total_prob,
                    "volume": vol,
                    "url": f"https://polymarket.com/market/{m.get('slug', '')}",
                })

            # Flag if YES price moved significantly
            last_price = float(m.get("lastTradePrice", 0) or yes_price)
            if last_price > 0.01:
                move = abs(yes_price - last_price) / last_price * 100
                if move > threshold_pct:
                    opportunities.append({
                        "type": "price_move",
                        "market": question,
                        "slug": m.get("slug", ""),
                        "current": yes_price,
                        "last": last_price,
                        "move_pct": move,
                        "volume": vol,
                        "url": f"https://polymarket.com/market/{m.get('slug', '')}",
                    })

        except (ValueError, IndexError):
            continue

    return {
        "opportunities": sorted(opportunities, key=lambda x: x["volume"], reverse=True)[:15],
        "scanned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_markets_scanned": len(markets),
    }


def scan_by_category() -> dict:
    """Return top markets per category."""
    results = {}
    build_token_cache(get_markets(limit=200))

    for label, tag in CATEGORIES.items():
        try:
            markets = get_sports_markets(sport=tag, limit=10)
            if not markets:
                markets = [m for m in get_markets(limit=200)
                           if tag.lower() in (m.get("tags", []) or []).lower()][:10]
            results[label] = [
                {
                    "question": m.get("question", "Unknown"),
                    "slug": m.get("slug", ""),
                    "yes_price": float(m.get("outcomePrices", [0])[0] or 0),
                    "volume_24h": float(m.get("volume24hr", 0) or 0),
                    "end_time": m.get("endTime", "Unknown"),
                    "url": f"https://polymarket.com/market/{m.get('slug', '')}",
                }
                for m in markets[:10]
                if float(m.get("volume24hr", 0) or 0) > 0
            ]
        except Exception:
            results[label] = []

    return results


def scan_closing_soon(hours: int = 6) -> list[dict]:
    """Markets resolving soon — useful for last-minute trading."""
    build_token_cache(get_markets(limit=500))
    markets = get_closing_soon(hours=hours, limit=20)
    return [
        {
            "question": m.get("question", "Unknown"),
            "slug": m.get("slug", ""),
            "yes_price": float(m.get("outcomePrices", [0])[0] or 0),
            "volume": float(m.get("volume24hr", 0) or 0),
            "end_time": m.get("endTime", "Unknown"),
            "url": f"https://polymarket.com/market/{m.get('slug', '')}",
        }
        for m in markets
    ]


def scan_soccer() -> list[dict]:
    """Dedicated soccer scanner — Imran's main interest."""
    all_markets = get_markets(limit=500)
    soccer = [m for m in all_markets
              if "football" in (m.get("question", "") + " " + " ".join(m.get("tags", []) or [])).lower()
              or "soccer" in (m.get("tags", []) or []).lower()
              or "epl" in (m.get("question", "") + " ".join(m.get("tags", []) or [])).lower()
              or "premier league" in (m.get("question", "") + " ".join(m.get("tags", []) or [])).lower()
              or "champions league" in (m.get("question", "") + " ".join(m.get("tags", []) or [])).lower()
              ]

    return [
        {
            "question": m.get("question", "Unknown"),
            "slug": m.get("slug", ""),
            "yes_price": float(m.get("outcomePrices", [0])[0] or 0),
            "no_price": float(m.get("outcomePrices", [0])[1] or 0) if len(m.get("outcomePrices", [])) > 1 else 0,
            "volume_24h": float(m.get("volume24hr", 0) or 0),
            "end_time": m.get("endTime", "Unknown"),
            "url": f"https://polymarket.com/market/{m.get('slug', '')}",
        }
        for m in soccer[:30]
    ]
