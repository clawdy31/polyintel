#!/usr/bin/env python3
"""
Morning Brief — scans opportunities + portfolio, sends to Telegram
Run: python morning_brief.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.scanner import scan_soccer, get_smart_alerts
from lib.fetcher import build_token_cache, get_markets, get_trending
from lib.notifier import send_daily_brief

def main():
    print("[morning_brief] Starting morning scan...")

    try:
        # Build cache
        markets = get_markets(limit=200)
        build_token_cache(markets)

        # Get soccer + trending
        soccer = scan_soccer()
        opportunities = get_smart_alerts(threshold_pct=5.0)

        top_opps = [
            {
                "question": o.get("market", o.get("question", "")),
                "yes_price": o.get("yes", o.get("yes_price", 0)),
                "volume_24h": o.get("volume", o.get("volume_24h", 0)),
            }
            for o in opportunities.get("opportunities", [])[:5]
        ]

        brief = {
            "total_value": 0,
            "total_pnl": 0,
            "cash": 0,
            "position_count": 0,
        }

        sent = send_daily_brief(top_opps, brief)
        if sent:
            print("[morning_brief] Sent successfully!")
        else:
            print("[morning_brief] No config or failed to send.")

    except Exception as e:
        print(f"[morning_brief] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
