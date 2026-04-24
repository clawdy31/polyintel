# 📊 PolyIntel — Polymarket Intelligence Dashboard

**Built by Clawdy AI for Imran** ⚡

A real-time portfolio monitoring and market intelligence dashboard for Polymarket traders. Runs locally, sends Telegram alerts, and scans for opportunities while you sleep.

---

## 🚀 Quick Start

```bash
cd ~/.openclaw/workspace/polyintel

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure (copy example + fill in your values)
cp config.example.py config.py
# Edit config.py — add your Telegram bot token + chat ID

# Run the dashboard
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## 📱 Telegram Alerts Setup

1. Open Telegram → chat with **@BotFather**
2. Send `/newbot` → give it a name → get your **bot token** (e.g. `123456789:ABC...`)
3. Open **@userinfobot** → get your **chat ID** (a number like `123456789`)
4. Add both to `config.py`:
   ```python
   TELEGRAM_BOT_TOKEN = "your_bot_token_here"
   TELEGRAM_CHAT_ID = "your_chat_id_here"
   ```

---

## ⚙️ Features

### 📈 Portfolio Page
- Live USDC.e + CLOB balance
- All positions with entry price, current price, P&L
- Bar chart of position-level P&L
- Auto-refresh every 60 seconds

### 🔥 Trending Page
- Top 30 markets by 24h volume
- YES/NO prices + spread
- Volume bar chart

### ⚽ Football Page
- All football/soccer markets (EPL, Champions League, La Liga, etc.)
- YES + NO pricing with 24h volume
- Resolve time + direct trade links

### 🔍 Market Scanner
- Detects **edge opportunities** (when YES + NO prices don't sum to $1.00)
- Flags **significant price moves** from last trade
- Configurable volume + move thresholds

### ⏰ Closing Soon
- Markets resolving within N hours (1–72h slider)
- Useful for last-minute trading before events

---

## 🔔 Alert System

Alerts fire when:
- A position moves ±5% (configurable) from your entry price
- Rate-limited: max 1 alert per position per hour

### Morning Brief
- Sends Telegram message every morning at 9 AM IST
- Includes portfolio summary + top opportunities

### Cron Setup (optional)
```bash
cd ~/.openclaw/workspace/polyintel
chmod +x setup_cron.sh
./setup_cron.sh
```

This sets up:
- Every 30 min → position alert check
- Every 2 hours → market cache refresh
- 9 AM IST daily → morning brief

---

## 📁 Project Structure

```
polyintel/
├── app.py              ← Main Streamlit app
├── config.py           ← Your credentials (copy from config.example.py)
├── config.example.py   ← Template
├── requirements.txt
├── README.md
├── setup_cron.sh      ← Cron setup script
├── lib/
│   ├── __init__.py
│   ├── fetcher.py     ← Polymarket API calls (Gamma + CLOB)
│   ├── portfolio.py   ← P&L calculations, position analysis
│   ├── scanner.py     ← Market opportunity detection
│   └── notifier.py    ← Telegram alert engine
├── scripts/
│   └── morning_brief.py ← Daily Telegram brief
└── logs/              ← Cron job logs
```

---

## 🔧 API Credentials

The app uses **Polymarket Gamma API** (public, no auth needed) for market data.
For **portfolio + positions**, you need CLOB credentials already in your `config.py`.

| Service | Auth | What's Needed |
|---------|------|---------------|
| Gamma API | None | Market data, prices, volume |
| CLOB API | L1+L2 sig | Your positions, orders, balance |
| Telegram | Bot token + Chat ID | Push notifications |

---

## ⚡ Imran's Setup Notes

- **Wallet:** `0xC218bc3e454d17AB2dA88E2F47DcBFe16E26dD7E`
- **CLOB Balance:** ~$10-11 USDC.e
- **Primary interest:** Football/Soccer markets (EPL, WC, etc.)
- **Alert threshold:** 5% price move from entry
