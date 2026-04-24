# What I Built (2026-04-25)

Built overnight while Imran slept. A full **Polymarket Intelligence Dashboard** from scratch.

## The Problem I Solved

Imran has a Polymarket trading setup but no good way to:
- See all his positions at a glance with live P&L
- Scan for football/soccer opportunities quickly
- Get alerted when his positions move significantly
- Find edge opportunities where YES + NO doesn't sum to $1.00

## What Was Built

### 📊 PolyIntel Dashboard
**Streamlit app at** `app.py` — dark themed, 5 pages:

| Page | What it does |
|------|-------------|
| **Portfolio** | Live positions, P&L, cash balance, bar chart |
| **Trending** | Top 30 markets by 24h volume |
| **Football** | Dedicated soccer scanner (EPL, Champions League, La Liga...) |
| **Market Scanner** | Edge detection + price move alerts |
| **Closing Soon** | Markets resolving in N hours (1-72h slider) |

### 🔔 Telegram Alert Engine
`lib/notifier.py` — sends alerts when:
- Position moves ±5% from entry (rate-limited: 1/hour)
- Morning brief at 9 AM IST with portfolio + opportunities

### 🔍 Market Scanner
`lib/scanner.py` — finds:
- **Edge opportunities** — when YES + NO prices don't sum to $1.00 (arb!)
- **Price moves** — significant deviations from last trade price
- **Soccer markets** — keyword-filtered for football interest

### 💼 Portfolio Analytics
`lib/portfolio.py` — clean position objects with P&L math

## Architecture

```
polyintel/
├── app.py              — Streamlit UI (dark theme)
├── config.py           — Credentials (Telegram, CLOB)
├── lib/
│   ├── fetcher.py     — Gamma + CLOB API calls
│   ├── portfolio.py   — Position/P&L calculations
│   ├── scanner.py     — Opportunity detection
│   └── notifier.py   — Telegram alert engine
├── scripts/
│   └── morning_brief.py — Daily Telegram brief
├── setup_cron.sh     — Cron job setup
└── venv/             — Python virtual environment
```

## To Run

```bash
cd ~/.openclaw/workspace/polyintel
source venv/bin/activate
streamlit run app.py
# Open http://localhost:8501
```

## Telegram Setup

1. Get bot token: Telegram → @BotFather → /newbot
2. Get chat ID: Telegram → @userinfobot
3. Add to config.py
4. Start getting alerts! 🔔

## GitHub

**https://github.com/clawdy31/polyintel**

---

*Built by Clawdy AI — 2026-04-25*
