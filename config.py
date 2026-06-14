import os
from dotenv import load_dotenv

# โหลดค่าต่างๆ จากไฟล์ .env
load_dotenv()

# ==========================================
# MaxPlus AI API Settings
# ==========================================
# ใส่ API Key ของคุณที่นี่ หรือในไฟล์ .env
MAXPLUS_API_KEY = os.getenv("MAXPLUS_API_KEY", "ccsk-YOUR_API_KEY_HERE")
MAXPLUS_BASE_URL = os.getenv("MAXPLUS_BASE_URL", "https://api.maxplus-ai.cc/v1")

# โมเดลที่ต้องการใช้งาน เช่น gpt-4o-mini, gpt-4o, claude-3-5-sonnet
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

# ==========================================
# MT5 Credentials (pre-filled in the dashboard login form)
# ==========================================
MT5_SERVER = os.getenv("MT5_SERVER", "")
MT5_LOGIN = os.getenv("MT5_LOGIN", "")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")

# ==========================================
# Trading Parameters
# ==========================================
# คู่เงินที่ต้องการเทรด (เช่น EURUSD, GBPUSD, XAUUSD)
SYMBOL = os.getenv("SYMBOL", "EURUSD")

# Timeframe สำหรับการวิเคราะห์ (M15, H1, H4, D1)
# สำหรับ MT5 จะใช้: mt5.TIMEFRAME_M15, mt5.TIMEFRAME_H1, mt5.TIMEFRAME_H4, mt5.TIMEFRAME_D1
TIMEFRAME_STR = os.getenv("TIMEFRAME", "H4")

# ขนาดสัญญาในการเทรด (Lot Size)
LOT_SIZE = float(os.getenv("LOT_SIZE", "0.01"))

# ==========================================
# Technical Indicator Parameters
# ==========================================
RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
MA_FAST_PERIOD = int(os.getenv("MA_FAST_PERIOD", "50"))
MA_SLOW_PERIOD = int(os.getenv("MA_SLOW_PERIOD", "200"))

# จำนวนแท่งเทียนย้อนหลังที่จะดึงมาวิเคราะห์
CANDLE_COUNT = int(os.getenv("CANDLE_COUNT", "20"))

# ==========================================
# Safety & Risk Management
# ==========================================
# อนุญาตให้บอทเปิดออเดอร์อัตโนมัติหรือไม่ (หากเป็น False จะทำงานในโหมด Dry-run/วิเคราะห์เท่านั้น)
AUTO_TRADE = os.getenv("AUTO_TRADE", "False").lower() in ("true", "1", "t", "yes")

# Max Spread ที่อนุญาตให้เปิดออเดอร์ได้ (ในหน่วย Points)
MAX_SPREAD = int(os.getenv("MAX_SPREAD", "50"))

# ==========================================
# Web Dashboard & Background Runner Settings
# ==========================================
# ระยะเวลาระหว่างการวิเคราะห์ตลาดของบอท (วินาที)
BOT_INTERVAL = int(os.getenv("BOT_INTERVAL", "60"))

# ค่าความมั่นใจขั้นต่ำของ AI (0-100) ที่จะอนุญาตให้เปิดออเดอร์
MIN_CONFIDENCE = int(os.getenv("MIN_CONFIDENCE", "70"))

# พอร์ตสำหรับรัน Web Dashboard (PORT takes precedence to support preview tools)
FLASK_PORT = int(os.getenv("PORT") or os.getenv("FLASK_PORT", "5000"))

