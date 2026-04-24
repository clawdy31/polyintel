#!/bin/bash
# Setup cron jobs for PolyIntel

POLYINTEL_DIR="$HOME/.openclaw/workspace/polyintel"
POLYINTEL_PY="$POLYINTEL_DIR/venv/bin/python3"

# Create venv if needed
if [ ! -f "$POLYINTEL_PY" ]; then
    python3 -m venv "$POLYINTEL_DIR/venv"
    "$POLYINTEL_PY" -m pip install -r "$POLYINTEL_DIR/requirements.txt" -q
fi

# Cron: Every 30 mins — check positions and send Telegram alerts
(crontab -l 2>/dev/null | grep -v "polyintel.*notifier"; echo "*/30 * * * * cd $POLYINTEL_DIR && $POLYINTEL_PY -m lib.notifier >> $POLYINTEL_DIR/logs/notifier.log 2>&1") | crontab -

# Cron: Every 2 hours — refresh market cache + scan opportunities
(crontab -l 2>/dev/null | grep -v "polyintel.*scanner"; echo "0 */2 * * * cd $POLYINTEL_DIR && $POLYINTEL_PY -m lib.scanner >> $POLYINTEL_DIR/logs/scanner.log 2>&1") | crontab -

# Cron: Every morning at 9 AM IST — send brief to Telegram
(crontab -l 2>/dev/null | grep -v "polyintel.*morning"; echo "0 9 * * * cd $POLYINTEL_DIR && $POLYINTEL_PY scripts/morning_brief.py >> $POLYINTEL_DIR/logs/brief.log 2>&1") | crontab -

echo "Cron jobs installed:"
crontab -l | grep polyintel
