# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Project

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then set MAXPLUS_API_KEY

# Start web dashboard (primary entry point)
python app.py          # http://localhost:5000

# Run a single analysis cycle via CLI (no web server)
python main.py

# Initialize database only
python database.py
```

On macOS/Linux the bot auto-enters **Mock Mode** — no MetaTrader5 install needed. On Windows, `pip install MetaTrader5` is also required.

## Architecture

The system has two runtime modes sharing the same codebase:

**Web mode** (`python app.py`): Flask + Socket.IO server that exposes REST endpoints and manages a `TradingBot` background thread. Real-time updates (account balance, AI decisions, trade events, console logs) are pushed to the frontend via Socket.IO events: `account_update`, `price_update`, `ai_decision`, `trade_update`, `bot_log`, `learning_update`.

**CLI mode** (`python main.py`): Runs `TradingBot.run_single_cycle()` once directly, useful for testing the analysis pipeline without the web server.

### Module responsibilities

| File | Role |
|---|---|
| `app.py` | Flask server, Socket.IO hub, REST API, bot lifecycle management |
| `main.py` | `TradingBot(Thread)` — trading loop, market data fetch, order execution, self-learning trigger |
| `ai_analyst.py` | `AIAnalyst` — calls MaxPlus AI API (OpenAI-compatible); auto-falls back to `_generate_mock_decision()` on API failure |
| `mt5_wrapper.py` | Platform abstraction: real `MetaTrader5` on Windows, `MockMT5` on macOS/Linux; selected at import time via `sys.platform` check |
| `config.py` | All settings loaded from `.env` via `python-dotenv`; values are module-level constants |
| `database.py` | SQLite helpers for three tables: `trades`, `trade_results`, `ai_learning_notes` |

### Trading cycle flow

Each `run_single_cycle()` call:
1. Connect MT5 (or Mock)
2. Check open trades in SQLite against live MT5 positions → close any that disappeared → trigger AI learning if ≥5 closed trades
3. Fetch account info → emit `account_update`
4. Get current tick → check spread against `MAX_SPREAD`
5. Pull 300 candles → compute RSI, MA_fast, MA_slow
6. Load latest AI learning notes from SQLite
7. Call `AIAnalyst.analyze_market()` → emit `ai_decision`
8. If BUY/SELL and `confidence ≥ MIN_CONFIDENCE` and no existing position and `AUTO_TRADE=True` → execute order → save to SQLite

### AI self-learning loop

After ≥5 closed trades accumulate, `check_and_trigger_learning()` spawns a thread that calls `AIAnalyst.generate_learning_summary()`. The resulting bullet-point notes are saved to `ai_learning_notes` in SQLite and injected into the system prompt on the next analysis cycle.

### Platform abstraction

`mt5_wrapper.py` sets the module-level `mt5` object at import time. All other modules do `from mt5_wrapper import mt5` and call it uniformly. `MockMT5` replicates the real MT5 API surface including simulated price movement, SL/TP checks, and order execution. The flag `mt5.IS_WINDOWS` is used in `main.py` when accessing real MT5 deal history.

## Key Configuration

All settings come from `.env` (loaded by `config.py`). Critical ones:

- `AUTO_TRADE` — defaults to `False` (dry-run). Set `True` only on Windows with a live MT5 connection.
- `MIN_CONFIDENCE` — AI signals below this % are skipped (default 70).
- `MAX_SPREAD` — orders skipped if spread exceeds this in points (default 50).
- `BOT_INTERVAL` — seconds between analysis cycles (default 60).
- `MAXPLUS_API_KEY` — if unset or left as placeholder, `AIAnalyst` auto-switches to mock signals.
