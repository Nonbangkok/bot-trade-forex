# 🤖 MaxPlus AI — MT5 Forex Trading Bot + Web Dashboard

บอทเทรด Forex บน MetaTrader 5 (MT5) ที่ขับเคลื่อนด้วย AI จาก MaxPlus AI API (GPT-4o, Claude ฯลฯ)
พร้อม **Web Dashboard** สำหรับควบคุมและติดตามผลแบบ Real-time และระบบ **AI Self-Learning**
ที่เรียนรู้จากผลการเทรดย้อนหลังเพื่อปรับปรุงสัญญาณในรอบถัดไป

โปรเจกต์รองรับ **Cross-Platform**:
- 🍎 **macOS / Linux:** โหมดจำลอง (Mock Mode) — พัฒนาและทดสอบได้โดยไม่ต้องติดตั้ง MT5
- 🪟 **Windows:** เชื่อมต่อ MT5 Terminal จริงและส่งออเดอร์อัตโนมัติ

---

## ✨ Features

| ฟีเจอร์ | รายละเอียด |
|---|---|
| 🖥️ **Web Dashboard** | หน้าเว็บ Dark Theme สไตล์ TradingView เปิดดูผ่าน Browser |
| 🔑 **MT5 Login UI** | ใส่ Server / Login ID / Password ผ่านฟอร์มบนเว็บ |
| 📊 **TradingView Charts** | กราฟแท่งเทียน Candlestick แบบ Realtime (Lightweight Charts) |
| 🤖 **AI Trade Analyst** | วิเคราะห์ RSI + EMA + ราคาผ่าน MaxPlus AI (GPT-4o-mini) |
| 🧠 **AI Self-Learning** | AI สรุปบทเรียนจากผลเทรดย้อนหลัง → นำกลับไปใช้ใน Prompt |
| 🎯 **Confidence Filter** | กรองเฉพาะสัญญาณที่ AI มั่นใจ ≥ MIN_CONFIDENCE% เท่านั้น |
| 📋 **Trade Journal** | บันทึกทุกออเดอร์ลง SQLite พร้อม P&L, SL, TP, Duration |
| 📡 **Real-time Logs** | Console แสดง Log บอทแบบ Live ผ่าน WebSocket |
| 📈 **Performance Stats** | Win Rate, Total P&L, Avg R:R Ratio |
| 🛡️ **Mock Fallback** | เมื่อ MaxPlus AI ล่ม บอทยังทำงานต่อด้วย Simulated AI |

---

## 📁 โครงสร้างไฟล์

```
bot-trade-forex/
├── app.py              # Flask Web Server + Socket.IO API
├── main.py             # TradingBot (Background Thread)
├── ai_analyst.py       # MaxPlus AI Client + Learning System
├── database.py         # SQLite Trade Journal Helper
├── mt5_wrapper.py      # MT5 Real/Mock Interface
├── config.py           # Settings & Environment Variables
├── templates/
│   └── index.html      # Web Dashboard UI
├── static/
│   ├── style.css       # Dark Theme CSS (Glassmorphism)
│   └── app.js          # Frontend Controller (WebSocket + Charts)
├── requirements.txt
├── .env                # API Keys & Secrets (ไม่ commit)
└── .env.example        # Template สำหรับตั้งค่า
```

---

## ⚙️ ตัวแปรใน `.env`

```env
# MaxPlus AI
MAXPLUS_API_KEY=ccsk-your-key-here
MAXPLUS_BASE_URL=https://api.maxplus-ai.cc/v1
MODEL_NAME=gpt-4o-mini

# Trading Parameters
SYMBOL=XAUUSD
TIMEFRAME=H4
LOT_SIZE=0.01
AUTO_TRADE=False          # True = ส่งออเดอร์จริง | False = Dry-run

# Risk Management
MAX_SPREAD=50
MIN_CONFIDENCE=70         # ขั้นต่ำ Confidence ของ AI (0-100)

# Indicator Settings
RSI_PERIOD=14
MA_FAST_PERIOD=50
MA_SLOW_PERIOD=200

# Dashboard Settings
FLASK_PORT=5000
BOT_INTERVAL=60           # รอบวิเคราะห์ตลาด (วินาที)
```

---

## 🚀 การติดตั้งและใช้งาน

### 1. Development บน macOS (Mock Mode)

```bash
# 1. Clone โปรเจกต์
git clone https://github.com/Nonbangkok/bot-trade-forex.git
cd bot-trade-forex

# 2. สร้าง Virtual Environment
python3 -m venv .venv
source .venv/bin/activate

# 3. ติดตั้ง Dependencies
pip install -r requirements.txt

# 4. ตั้งค่า Environment
cp .env.example .env
# แก้ MAXPLUS_API_KEY ในไฟล์ .env ให้ถูกต้อง

# 5. รัน Web Dashboard
python app.py
```

เปิด Browser → **http://localhost:5000**

---

### 2. Production บน Windows (MT5 จริง)

```bash
# 1. ติดตั้ง Dependencies รวม MetaTrader5
pip install -r requirements.txt
pip install MetaTrader5

# 2. ตั้งค่า .env
AUTO_TRADE=True
BOT_INTERVAL=300   # แนะนำ 5 นาที (300 วินาที)

# 3. รัน Web Dashboard
python app.py
```

1. เปิด Browser → **http://localhost:5000**
2. กรอก **MT5 Server**, **Login ID**, **Password** ในฟอร์ม "Connect to MetaTrader 5"
3. เลือก Symbol และ Timeframe
4. กด **Start Bot**

---

## 🖥️ Web Dashboard Guide

| ส่วน | คำอธิบาย |
|---|---|
| **Header** | แสดง Balance, Equity, Free Margin, สถานะบอท (🟢/🔴) |
| **Connect MT5** | Login ผ่านเว็บ ไม่ต้องแก้ไข config |
| **Market Chart** | กราฟแท่งเทียน EURUSD/GBPUSD/XAUUSD แบบ Realtime |
| **Bot Controls** | เลือก Symbol + Timeframe → Start/Stop/Analyze Now |
| **AI Analyst** | แสดง BUY/SELL/HOLD + Confidence% + เหตุผลล่าสุด |
| **Learning Notes** | บทสรุปที่ AI เรียนรู้จากผลการเทรดย้อนหลัง |
| **Performance** | สรุป Win Rate, Net P&L, Avg R:R |
| **Trade Journal** | ตารางประวัติออเดอร์ทั้งหมด + ผล WIN/LOSS |
| **Live Console** | Log แบบ Realtime ผ่าน WebSocket |

---

## 🧠 ระบบ AI Self-Learning

```
เปิดออเดอร์ → บันทึกลง SQLite
    ↓
ออเดอร์ปิด (ชน SL/TP) → บันทึกผล (WIN/LOSS/BE)
    ↓
สะสมครบ 5+ ออเดอร์ → ส่งผลให้ AI สรุป "Learning Notes"
    ↓
Learning Notes → ใส่ใน System Prompt รอบวิเคราะห์ถัดไป
    ↓
AI ปรับปรุงการตัดสินใจจากประสบการณ์จริง ♻️
```

---

## 📡 API Endpoints

| Method | Endpoint | คำอธิบาย |
|---|---|---|
| `POST` | `/api/mt5/login` | เชื่อมต่อ MT5 |
| `GET` | `/api/mt5/status` | สถานะบัญชี |
| `GET` | `/api/chart/data` | ข้อมูลแท่งเทียน |
| `GET` | `/api/trades` | ประวัติการเทรดทั้งหมด |
| `GET` | `/api/stats` | สถิติผลการเทรด |
| `POST` | `/api/bot/start` | เริ่มรันบอท |
| `POST` | `/api/bot/stop` | หยุดบอท |
| `GET` | `/api/bot/status` | สถานะบอทปัจจุบัน |
| `POST` | `/api/bot/analyze-now` | วิเคราะห์ตลาดทันที |
| `GET` | `/api/learning/notes` | ดู Learning Notes ล่าสุด |
| `POST` | `/api/learning/generate` | สั่ง AI สรุป Learning Notes |

---

## ⚠️ ข้อควรระวัง & ความปลอดภัย

- 🔐 **API Key:** อย่า commit ไฟล์ `.env` ขึ้น Git เด็ดขาด (ระบบ `.gitignore` ป้องกันแล้ว)
- 💰 **Demo First:** ทดสอบด้วยบัญชี Demo อย่างน้อย 1-2 สัปดาห์ก่อนใช้เงินจริง
- 🎚️ **AUTO_TRADE=False:** ค่าเริ่มต้นเป็น Dry-run — AI วิเคราะห์แต่ไม่ส่งออเดอร์
- 📊 **MIN_CONFIDENCE:** ตั้งค่า 70-80 เพื่อกรองสัญญาณคุณภาพต่ำออก
- 🤖 **Mock Fallback:** หาก MaxPlus AI API ล่ม บอทจะจำลองสัญญาณต่อโดยอัตโนมัติ

---

## 🛠️ Tech Stack

| ส่วน | เทคโนโลยี |
|---|---|
| Backend | Python 3.10+, Flask, Flask-SocketIO |
| Frontend | Vanilla HTML/CSS/JS, TradingView Lightweight Charts |
| Database | SQLite (via built-in `sqlite3`) |
| AI | MaxPlus AI API (OpenAI-compatible) |
| MT5 | MetaTrader5 Python library (Windows only) |
| Realtime | WebSocket via Socket.IO |

---

> **หมายเหตุ:** ไลบรารี `MetaTrader5` รองรับเฉพาะ **Windows** เท่านั้น
> บน macOS/Linux ระบบจะเข้าโหมด Mock อัตโนมัติ
