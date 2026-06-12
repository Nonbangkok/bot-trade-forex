import time
import pandas as pd
import numpy as np
import logging
import threading
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

class TradingBot(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self._stop_event = threading.Event()
        self._running = False
        self.socketio = None # จะตั้งค่าโดย app.py เพื่อส่ง real-time updates
        self.symbol = config.SYMBOL
        self.timeframe = config.TIMEFRAME_STR
        self.analyst = AIAnalyst()

    def set_socketio(self, socketio):
        self.socketio = socketio

    def stop(self):
        self._stop_event.set()
        self._running = False

    def is_running(self):
        return self._running

    def log_message(self, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted = f"{timestamp} - {message}"
        logging.info(message)
        if self.socketio:
            self.socketio.emit('bot_log', {'message': formatted})

    def run(self):
        self._running = True
        import database
        database.init_db()
        self.log_message("🟢 Trading Bot Thread Started.")
        
        while not self._stop_event.is_set():
            try:
                self.run_single_cycle()
            except Exception as e:
                self.log_message(f"❌ Error in trading cycle: {e}")
                
            # หน่วงเวลาก่อนสแกนรอบใหม่ (ดึงค่าจาก config)
            self._stop_event.wait(config.BOT_INTERVAL)
            
        self._running = False
        self.log_message("🔴 Trading Bot Thread Stopped.")

    def run_single_cycle(self):
        import database
        self.log_message(f"⏳ เริ่มต้นรอบการวิเคราะห์ตลาด ({self.symbol} - {self.timeframe})")
        
        # 1. เชื่อมต่อ MT5
        if not mt5.initialize():
            self.log_message("❌ ไม่สามารถเชื่อมต่อกับ MT5 Terminal ได้")
            return

        try:
            # 2. ตรวจสอบสถานะการปิดออเดอร์ของคู่เงินที่เราเทรด
            self.check_and_update_closed_trades()

            # 3. ดึงข้อมูลพอร์ตการลงทุน
            account = mt5.account_info()
            if account is None:
                self.log_message("❌ ไม่สามารถดึงข้อมูลบัญชีเทรดได้")
                return
            
            # ส่งผลลัพธ์ข้อมูลพอร์ตไปยังเว็บหน้าบ้าน
            if self.socketio:
                self.socketio.emit('account_update', {
                    'login': account.login,
                    'balance': account.balance,
                    'equity': account.equity,
                    'margin_free': account.margin_free,
                    'currency': getattr(account, "currency", "USD")
                })

            # 4. ตรวจสอบการเปิดตำแหน่งซื้อขายค้างไว้ (ป้องกันการเปิดออเดอร์ซ้ำซ้อน)
            active_positions = check_existing_positions(self.symbol)
            self.log_message(f"📊 ออเดอร์ที่ถืออยู่ของ {self.symbol}: {active_positions} ออเดอร์")
            
            # ดึงราคาเสนอซื้อเสนอขายปัจจุบัน
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                self.log_message(f"❌ ไม่สามารถดึงข้อมูลราคาของคู่เงิน {self.symbol} ได้")
                return
                
            current_price = {"bid": tick.bid, "ask": tick.ask}
            spread = round((tick.ask - tick.bid) / mt5.symbol_info(self.symbol).point)
            
            # ส่งราคาปัจจุบันขึ้นหน้าบ้าน
            if self.socketio:
                self.socketio.emit('price_update', {
                    'symbol': self.symbol,
                    'bid': tick.bid,
                    'ask': tick.ask,
                    'time': int(time.time() * 1000)
                })
                
            self.log_message(f"💵 ราคาตลาดปัจจุบัน {self.symbol} Bid: {tick.bid:.5f} | Ask: {tick.ask:.5f} (Spread: {spread} points)")

            # ป้องกันเทรดหาก Spread สูงเกินเกณฑ์ความปลอดภัย
            if spread > config.MAX_SPREAD:
                self.log_message(f"⚠️ Spread ({spread}) สูงเกินกว่าเกณฑ์ความปลอดภัย ({config.MAX_SPREAD}) - ข้ามการเทรดรอบนี้")
                return

            # 5. ดึงข้อมูลตลาดและคำนวณอินดิเคเตอร์
            self.log_message(f"📈 ดึงข้อมูลแท่งเทียนย้อนหลังและคำนวณอินดิเคเตอร์สำหรับ {self.symbol} ({self.timeframe})...")
            df_candles = get_market_data(self.symbol, self.timeframe)
            if df_candles is None:
                return

            # 6. ดึง Learning Notes ล่าสุดเพื่อปรับปรุงประสิทธิภาพ AI
            latest_note = database.get_latest_learning_note()
            learning_context = latest_note['notes'] if latest_note else None
            if learning_context:
                self.log_message("🧠 นำเข้า AI Learning Notes เพื่อประกอบการตัดสินใจ")

            # 7. ส่งวิเคราะห์ตลาดผ่าน MaxPlus AI
            decision = self.analyst.analyze_market(
                symbol=self.symbol,
                timeframe=self.timeframe,
                current_price=current_price,
                current_spread=spread,
                df_candles=df_candles,
                learning_notes=learning_context
            )

            recommendation = decision.get("recommendation", "HOLD")
            reasoning = decision.get("reasoning", "No reason provided")
            confidence = decision.get("confidence_score", 0)
            
            # ส่งผลวิเคราะห์ AI ขึ้นหน้าบ้าน
            if self.socketio:
                self.socketio.emit('ai_decision', {
                    'recommendation': recommendation,
                    'reasoning': reasoning,
                    'confidence': confidence,
                    'time': datetime.now().strftime('%H:%M:%S')
                })
            
            # 8. ตัดสินใจสั่งเปิดออเดอร์
            if recommendation in ["BUY", "SELL"]:
                if active_positions > 0:
                    self.log_message(f"⏭️ AI แนะนำ {recommendation} (ความมั่นใจ {confidence}%) แต่ข้ามไป เนื่องจากมีออเดอร์ของ {self.symbol} เปิดค้างไว้แล้ว")
                elif confidence < config.MIN_CONFIDENCE:
                    self.log_message(f"⏭️ AI แนะนำ {recommendation} (ความมั่นใจ {confidence}%) แต่ข้ามไป เนื่องจากต่ำกว่าค่าเกณฑ์ความมั่นใจ ({config.MIN_CONFIDENCE}%)")
                elif not config.AUTO_TRADE:
                    self.log_message(f"📝 AI แนะนำ {recommendation} | ความมั่นใจ {confidence}% (SL {decision.get('sl_pips')} pips, TP {decision.get('tp_pips')} pips)")
                    self.log_message("⏭️ ข้ามการเปิดออเดอร์ เนื่องจากไม่ได้เปิดระบบ AUTO_TRADE (โหมด Dry-run)")
                else:
                    sl_pips = float(decision.get("sl_pips", 30))
                    tp_pips = float(decision.get("tp_pips", 60))
                    
                    # ส่งคำสั่งเทรดเข้า MT5
                    success, ticket_id, executed_price = self.execute_trade_with_ticket(
                        self.symbol, recommendation, current_price, sl_pips, tp_pips
                    )
                    
                    if success:
                        # คำนวณ SL / TP บนราคาจริง
                        pip_size = get_pip_size(self.symbol, mt5.symbol_info(self.symbol).digits)
                        sl_price = executed_price - (sl_pips * pip_size) if recommendation == 'BUY' else executed_price + (sl_pips * pip_size)
                        tp_price = executed_price + (tp_pips * pip_size) if recommendation == 'BUY' else executed_price - (tp_pips * pip_size)
                        
                        # บันทึกลงฐานข้อมูล SQLite
                        db_id = database.save_trade(
                            ticket_id=ticket_id,
                            symbol=self.symbol,
                            action=recommendation,
                            entry_price=executed_price,
                            sl=round(sl_price, mt5.symbol_info(self.symbol).digits),
                            tp=round(tp_price, mt5.symbol_info(self.symbol).digits),
                            lot_size=config.LOT_SIZE,
                            confidence=confidence,
                            reasoning=reasoning,
                            status="OPEN"
                        )
                        self.log_message(f"✅ บันทึกออเดอร์ Ticket {ticket_id} ลงฐานข้อมูลสำเร็จ (DB ID: {db_id})")
                        
                        # แจ้งเตือนหน้าบ้านให้อัปเดตตารางรายการเทรด
                        if self.socketio:
                            self.socketio.emit('trade_update', {'status': 'opened', 'ticket_id': ticket_id})
            else:
                self.log_message(f"😴 AI แนะนำ: HOLD (ไม่มีสัญญาณเทรดที่น่าสนใจ) | เหตุผล: {reasoning}")

        except Exception as e:
            self.log_message(f"❌ เกิดข้อผิดพลาดในระบบวิเคราะห์: {e}")
        finally:
            mt5.shutdown()
            self.log_message("🏁 จบรอบการวิเคราะห์")

    def check_and_update_closed_trades(self):
        """ตรวจสอบและอัปเดตออเดอร์ใน SQLite ที่ปิดแล้ว"""
        import database
        open_trades = database.get_open_trades()
        if not open_trades:
            return
            
        # ดึง active positions จาก MT5
        active_positions = mt5.positions_get()
        active_tickets = {pos.ticket for pos in active_positions}
        
        for trade in open_trades:
            ticket = trade['ticket_id']
            # หาก ticket ไม่แสดงในรายการเปิดบน MT5 แปลว่าถูกปิดแล้ว
            if ticket not in active_tickets:
                self.log_message(f"🔔 ออเดอร์ Ticket {ticket} ถูกปิดตัวลงแล้ว กำลังคำนวณผลลัพธ์...")
                
                exit_price = trade['entry_price']
                pnl_usd = 0.0
                pnl_pips = 0.0
                outcome = 'BE'
                
                # หากใช้งานบน Windows ค้นหาดีลจริง
                if mt5.IS_WINDOWS:
                    import MetaTrader5 as mt5_real
                    history_deals = mt5_real.history_deals_get(ticket=ticket)
                    if history_deals and len(history_deals) > 0:
                        close_deal = None
                        for deal in history_deals:
                            if deal.entry == 1: # DEAL_ENTRY_OUT (การปิดออเดอร์)
                                close_deal = deal
                                break
                        if close_deal:
                            exit_price = close_deal.price
                            pnl_usd = close_deal.profit
                            pip_size = get_pip_size(trade['symbol'], mt5_real.symbol_info(trade['symbol']).digits)
                            pnl_pips = (exit_price - trade['entry_price']) / pip_size if trade['action'] == 'BUY' else (trade['entry_price'] - exit_price) / pip_size
                            outcome = 'WIN' if pnl_usd > 0 else ('LOSS' if pnl_usd < 0 else 'BE')
                else:
                    # ใน macOS Mock mode จำลองจุดปิด (วิน/ลอส) เพื่อผลลัพธ์ที่เสมือนจริง
                    import random
                    outcome = random.choice(['WIN', 'LOSS'])
                    pip_size = get_pip_size(trade['symbol'], mt5.symbol_info(trade['symbol']).digits)
                    if outcome == 'WIN':
                        exit_price = trade['tp'] if trade['tp'] else (trade['entry_price'] + 50 * pip_size if trade['action'] == 'BUY' else trade['entry_price'] - 50 * pip_size)
                    else:
                        exit_price = trade['sl'] if trade['sl'] else (trade['entry_price'] - 30 * pip_size if trade['action'] == 'BUY' else trade['entry_price'] + 30 * pip_size)
                    
                    pnl_pips = (exit_price - trade['entry_price']) / pip_size if trade['action'] == 'BUY' else (trade['entry_price'] - exit_price) / pip_size
                    pip_mult = 100000 if "XAU" not in trade['symbol'] else 100
                    pnl_usd = (exit_price - trade['entry_price']) * pip_mult * trade['lot_size'] if trade['action'] == 'BUY' else (trade['entry_price'] - exit_price) * pip_mult * trade['lot_size']

                # หาช่วงเวลาเวลาถือครอง
                entry_dt = datetime.strptime(trade['timestamp'], '%Y-%m-%d %H:%M:%S')
                duration = int(time.time() - entry_dt.timestamp())
                
                # บันทึกผลลัพธ์ลง SQLite
                database.update_trade_result(
                    trade_id=trade['id'],
                    exit_price=exit_price,
                    pnl_pips=pnl_pips,
                    pnl_usd=pnl_usd,
                    duration=duration,
                    outcome=outcome
                )
                self.log_message(f"💰 ออเดอร์ ID {trade['id']} (Ticket {ticket}) ปิดดีลแล้ว: {outcome} | P&L: {pnl_usd:.2f} USD ({pnl_pips:.1f} pips)")
                
                # เช็คผลและรันระบบ AI Self-Learning
                self.check_and_trigger_learning()
                
                if self.socketio:
                    self.socketio.emit('trade_update', {'status': 'closed', 'ticket_id': ticket, 'pnl': pnl_usd})

    def check_and_trigger_learning(self):
        """วิเคราะห์สถิติเพื่อป้อนการเรียนรู้ให้ AI"""
        import database
        closed_trades = [t for t in database.get_recent_trades(limit=10) if t['status'] == 'CLOSED']
        if len(closed_trades) >= 5:
            self.log_message(f"🧠 ตรวจพบออเดอร์ปิดแล้วสะสม {len(closed_trades)} ออเดอร์ เริ่มกระบวนการเรียนรู้และสรุปข้อตกลงของ AI...")
            try:
                def run_learning():
                    notes = self.analyst.generate_learning_summary(closed_trades)
                    database.save_learning_note(notes, len(closed_trades))
                    self.log_message("✅ AI เรียนรู้เสร็จสมบูรณ์และได้สร้าง Learning Notes ใหม่เรียบร้อยแล้ว!")
                    if self.socketio:
                        self.socketio.emit('learning_update', {'notes': notes})
                
                t = threading.Thread(target=run_learning)
                t.start()
            except Exception as e:
                self.log_message(f"❌ ไม่สามารถรันระบบเรียนรู้ของ AI ได้: {e}")

    def execute_trade_with_ticket(self, symbol, action_type, current_price, sl_pips, tp_pips):
        """ส่งคำสั่งเทรดเข้า MT5 และนำผลตอบกลับสำเร็จพร้อมไอดี Ticket และราคาที่แท้จริง"""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self.log_message(f"❌ ไม่พบข้อมูลคู่เงิน {symbol}")
            return False, 0, 0.0

        digits = symbol_info.digits
        point = symbol_info.point
        pip_size = get_pip_size(symbol, digits)

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
            return False, 0, 0.0

        price = round(price, digits)
        sl = round(sl, digits)
        tp = round(tp, digits)

        filling_type = mt5.ORDER_FILLING_FOK
        if symbol_info.filling_mode & 1:
            filling_type = mt5.ORDER_FILLING_FOK
        elif symbol_info.filling_mode & 2:
            filling_type = mt5.ORDER_FILLING_IOC
        else:
            filling_type = mt5.ORDER_FILLING_RETURN

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
            "type_time": 0,
            "type_filling": filling_type,
        }

        self.log_message(f"🚀 ส่งคำสั่งเทรด: {action_type} {config.LOT_SIZE} {symbol} ที่ราคา {price} (SL: {sl}, TP: {tp})")
        
        result = mt5.order_send(request)
        if result is None:
            self.log_message("❌ การส่งคำสั่งล้มเหลว (ส่งคำขอไม่สำเร็จ)")
            return False, 0, 0.0

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.log_message(f"❌ โบรกเกอร์ปฏิเสธคำสั่งเทรด! Code: {result.retcode}, Comment: {result.comment}")
            return False, 0, 0.0
            
        self.log_message(f"✅ เปิดออเดอร์สำเร็จ! Order Ticket ID: {result.order}")
        return True, result.order, result.price

if __name__ == "__main__":
    # รันบอทในโหมด CLI ปกติสำหรับรันแบบเดี่ยว
    print("Starting bot in CLI mode...")
    bot = TradingBot()
    bot.run_single_cycle()
