import time
import pandas as pd
import numpy as np
import logging
from datetime import datetime

# นำเข้าองค์ประกอบต่างๆ ของโปรเจกต์
import config
from mt5_wrapper import mt5
from ai_analyst import AIAnalyst

# ตั้งค่า Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot_trader.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def get_timeframe_value(tf_str):
    """แปลงข้อความ Timeframe เป็นค่าคงที่ของ MT5"""
    tf_map = {
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1
    }
    return tf_map.get(tf_str, mt5.TIMEFRAME_H4)

def get_pip_size(symbol, digits):
    """คำนวณขนาดของ 1 Pip สำหรับคู่เงินหรือสินทรัพย์ต่างๆ"""
    if "JPY" in symbol:
        return 0.01
    elif "XAU" in symbol or "GOLD" in symbol:
        return 0.1  # สำหรับทองคำ 1 pip มักหมายถึง 0.1 USD
    elif digits == 3 or digits == 2:
        return 0.01
    elif digits == 5 or digits == 4:
        return 0.0001
    else:
        return 0.0001

def calculate_rsi(series, period=14):
    """คำนวณดัชนี RSI (Relative Strength Index) แบบดั้งเดิม"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_market_data(symbol, timeframe_str):
    """ดึงข้อมูลราคาประวัติศาสตร์จาก MT5 และประมวลผลอินดิเคเตอร์"""
    tf = get_timeframe_value(timeframe_str)
    
    # ดึงข้อมูลมา 300 แท่ง เพื่อให้มีข้อมูลมากพอในการคำนวณอินดิเคเตอร์ช่วงยาว เช่น MA 200
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, 300)
    if rates is None or len(rates) == 0:
        logging.error(f"❌ ไม่สามารถดึงข้อมูลราคาสำหรับ {symbol} ({timeframe_str})")
        return None
    
    # แปลงเป็น Pandas DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['time_str'] = df['time'].dt.strftime('%Y-%m-%d %H:%M')
    
    # คำนวณอินดิเคเตอร์ทางเทคนิค
    df['rsi'] = calculate_rsi(df['close'], config.RSI_PERIOD)
    df['ma_fast'] = df['close'].rolling(window=config.MA_FAST_PERIOD).mean()
    df['ma_slow'] = df['close'].rolling(window=config.MA_SLOW_PERIOD).mean()
    
    return df

def check_existing_positions(symbol):
    """ตรวจสอบว่ามีออเดอร์ของคู่เงินนี้เปิดค้างอยู่หรือไม่"""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return 0
    return len(positions)

def execute_trade(symbol, action_type, current_price, sl_pips, tp_pips):
    """ส่งคำสั่งซื้อขายเข้า MT5 พร้อมตั้ง SL/TP"""
    # ดึงข้อมูลสัญลักษณ์เงินเพื่อเช็คจำนวนทศนิยม
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logging.error(f"❌ ไม่พบข้อมูลสัญลักษณ์ {symbol}")
        return False

    digits = symbol_info.digits
    point = symbol_info.point
    pip_size = get_pip_size(symbol, digits)

    # กำหนดประเภทคำสั่งและระดับราคาซื้อขาย
    if action_type == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
        price = current_price['ask']
        sl = price - (sl_pips * pip_size)
        tp = price + (tp_pips * pip_size)
    elif action_type == "SELL":
        order_type = mt5.ORDER_TYPE_SELL
        price = current_price['bid']
        sl = price + (sl_pips * pip_size)
        tp = price - (tp_pips * pip_size)
    else:
        return False

    # ปัดเศษทศนิยมราคาให้ถูกต้องตามข้อกำหนดของโบรกเกอร์
    price = round(price, digits)
    sl = round(sl, digits)
    tp = round(tp, digits)

    # ตรวจสอบการรองรับรูปแบบ Order Filling ของโบรกเกอร์ (IOC หรือ FOK)
    filling_type = mt5.ORDER_FILLING_FOK
    if symbol_info.filling_mode & 1:
        filling_type = mt5.ORDER_FILLING_FOK
    elif symbol_info.filling_mode & 2:
        filling_type = mt5.ORDER_FILLING_IOC
    else:
        filling_type = mt5.ORDER_FILLING_RETURN

    # สร้างโครงสร้างคำสั่งส่งเทรด
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": config.LOT_SIZE,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 987654,
        "comment": "MaxPlus AI Trade",
        "type_time": 0, # Good till Cancelled
        "type_filling": filling_type,
    }

    logging.info(f"🚀 ส่งคำสั่งซื้อขาย: {action_type} {config.LOT_SIZE} {symbol} ที่ราคา {price} (SL: {sl}, TP: {tp})")
    
    # ส่งคำสั่งเข้า MT5
    result = mt5.order_send(request)
    if result is None:
        logging.error("❌ การส่งคำสั่งล้มเหลว (ส่งคำขอไม่สำเร็จ)")
        return False

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"❌ โบรกเกอร์ปฏิเสธคำสั่งซื้อขาย! Code: {result.retcode}, Comment: {result.comment}")
        return False
        
    logging.info(f"✅ เปิดออเดอร์สำเร็จ! Order ID: {result.order}")
    return True

def run_trading_bot():
    """ฟังก์ชันการทำงานหลักรอบเดียว"""
    logging.info("--------------------------------------------------")
    logging.info(f"⏳ เริ่มต้นทำงาน ณ เวลา: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. เชื่อมต่อ MT5
    if not mt5.initialize():
        logging.error("❌ ไม่สามารถเชื่อมต่อกับ MT5 Terminal ได้")
        return

    try:
        # 2. ตรวจสอบข้อมูลพอร์ตการลงทุน
        account = mt5.account_info()
        if account is None:
            logging.error("❌ ไม่สามารถดึงข้อมูลบัญชีเทรดได้")
            return
        logging.info(f"💳 พอร์ตลงทุน: ID {account.login} | ยอดเงินคงเหลือ: {account.balance} {account.currency} | Equity: {account.equity}")

        # 3. ตรวจสอบการเปิดตำแหน่งซื้อขายค้างไว้ (ป้องการเปิดออเดอร์ซ้ำซ้อน)
        active_positions = check_existing_positions(config.SYMBOL)
        logging.info(f"📊 จำนวนออเดอร์ที่ถืออยู่ของ {config.SYMBOL}: {active_positions} ออเดอร์")
        
        # ดึงราคาเสนอซื้อเสนอขายปัจจุบัน
        tick = mt5.symbol_info_tick(config.SYMBOL)
        if tick is None:
            logging.error(f"❌ ไม่สามารถดึงข้อมูลราคาของคู่เงิน {config.SYMBOL} ได้")
            return
            
        current_price = {"bid": tick.bid, "ask": tick.ask}
        spread = round((tick.ask - tick.bid) / mt5.symbol_info(config.SYMBOL).point)
        logging.info(f"💵 ราคาตลาดปัจจุบัน {config.SYMBOL} Bid: {tick.bid:.5f} | Ask: {tick.ask:.5f} (Spread: {spread} points)")

        # ป้องกันเทรดหาก Spread สูงเกินไปในช่วงข่าวแรงหรือตลาดเปิด/ปิด
        if spread > config.MAX_SPREAD:
            logging.warning(f"⚠️ Spread ({spread}) สูงเกินกว่าเกณฑ์ความปลอดภัยที่กำหนด ({config.MAX_SPREAD}) - ข้ามการเทรดรอบนี้")
            return

        # 4. ดึงข้อมูลตลาดและอินดิเคเตอร์
        logging.info(f"📈 ดึงข้อมูลแท่งเทียนย้อนหลังและคำนวณอินดิเคเตอร์สำหรับ {config.SYMBOL} ({config.TIMEFRAME_STR})...")
        df_candles = get_market_data(config.SYMBOL, config.TIMEFRAME_STR)
        if df_candles is None:
            return

        # 5. ให้ AI วิเคราะห์ผ่าน MaxPlus AI API
        analyst = AIAnalyst()
        decision = analyst.analyze_market(
            symbol=config.SYMBOL,
            timeframe=config.TIMEFRAME_STR,
            current_price=current_price,
            current_spread=spread,
            df_candles=df_candles
        )

        recommendation = decision.get("recommendation", "HOLD")
        reasoning = decision.get("reasoning", "No reason provided")
        
        # 6. ตัดสินใจสั่งเปิดออเดอร์
        if recommendation in ["BUY", "SELL"]:
            if active_positions > 0:
                logging.info(f"⏭️ AI แนะนำ {recommendation} แต่ข้ามไป เนื่องจากมีออเดอร์ของ {config.SYMBOL} เปิดค้างไว้แล้ว")
            elif not config.AUTO_TRADE:
                logging.info(f"📝 AI แนะนำ {recommendation} (SL {decision.get('sl_pips')} pips, TP {decision.get('tp_pips')} pips)")
                logging.info("⏭️ ข้ามการเปิดออเดอร์ เนื่องจากไม่ได้เปิดระบบ AUTO_TRADE (โหมด Dry-run)")
            else:
                sl_pips = float(decision.get("sl_pips", 30))
                tp_pips = float(decision.get("tp_pips", 60))
                execute_trade(config.SYMBOL, recommendation, current_price, sl_pips, tp_pips)
        else:
            logging.info(f"😴 AI แนะนำ: HOLD (ไม่มีแนวโน้มที่น่าสนใจ) | เหตุผล: {reasoning}")

    except Exception as e:
        logging.error(f"❌ เกิดข้อผิดพลาดในระบบบอท: {e}", exc_info=True)
    finally:
        # ปิดการเชื่อมต่อ
        mt5.shutdown()
        logging.info("🏁 จบการทำงานในรอบนี้")

if __name__ == "__main__":
    # รันบอทเทรดรอบแรก
    run_trading_bot()
    
    # หากต้องการให้รันเป็นรอบเวลา ทุกๆ 5 นาที (ตัวอย่าง) สามารถปลดคอมเมนต์บรรทัดด้านล่าง
    # while True:
    #     run_trading_bot()
    #     time.sleep(300) # รอ 300 วินาที (5 นาที)
