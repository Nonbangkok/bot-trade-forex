import os
import threading
import logging
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

import config
import database
from mt5_wrapper import mt5, initialize_with_login, get_account_summary
from main import TradingBot, get_timeframe_value

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bot-forex-trade-secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# ตัวแปรควบคุมบอทใน Background
bot = None
bot_lock = threading.Lock()

def get_or_create_bot():
    global bot
    with bot_lock:
        if bot is None or not bot.is_alive():
            bot = TradingBot()
            bot.set_socketio(socketio)
        return bot

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/mt5/login', methods=['POST'])
def mt5_login():
    data = request.json or {}
    server = data.get('server')
    login = data.get('login')
    password = data.get('password')
    
    if not server or not login or not password:
        return jsonify({"success": False, "message": "ข้อมูลไม่ครบถ้วน กรุณากรอกข้อมูลให้ครบทุกช่อง"}), 400
        
    logging.info(f"Attempting login to MT5 server {server} with account {login}")
    success = initialize_with_login(server, login, password)
    
    if success:
        summary = get_account_summary()
        socketio.emit('account_update', summary)
        return jsonify({"success": True, "message": "เชื่อมต่อ MT5 สำเร็จ", "account": summary})
    else:
        return jsonify({"success": False, "message": "ไม่สามารถล็อกอินหรือเชื่อมต่อ MT5 ได้ กรุณาตรวจสอบข้อมูลอีกครั้ง"})

@app.route('/api/mt5/status', methods=['GET'])
def mt5_status():
    summary = get_account_summary()
    return jsonify(summary)

@app.route('/api/chart/data', methods=['GET'])
def chart_data():
    current_bot = get_or_create_bot()
    symbol = request.args.get('symbol', current_bot.symbol)
    timeframe_str = request.args.get('timeframe', current_bot.timeframe)
    
    # เชื่อมต่อ MT5 ชั่วคราวเพื่อดึงข้อมูลกราฟ
    if not mt5.initialize():
        return jsonify({"error": "Failed to connect to MT5"}), 500
        
    tf = get_timeframe_value(timeframe_str)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, 100)
    mt5.shutdown()
    
    if rates is None or len(rates) == 0:
        return jsonify([])
        
    chart_candles = []
    for r in rates:
        chart_candles.append({
            'time': int(r['time']), # unix timestamp in seconds
            'open': float(r['open']),
            'high': float(r['high']),
            'low': float(r['low']),
            'close': float(r['close'])
        })
    return jsonify(chart_candles)

@app.route('/api/trades', methods=['GET'])
def get_trades():
    trades = database.get_recent_trades(limit=50)
    return jsonify(trades)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    stats = database.get_performance_stats()
    return jsonify(stats)

@app.route('/api/bot/start', methods=['POST'])
def bot_start():
    global bot
    with bot_lock:
        if bot and bot.is_alive() and bot.is_running():
            return jsonify({"success": True, "message": "บอทกำลังทำงานอยู่แล้ว"})
            
        data = request.json or {}
        symbol = data.get('symbol', config.SYMBOL)
        timeframe = data.get('timeframe', config.TIMEFRAME_STR)
        
        # ตั้งค่าสัญลักษณ์และไทม์เฟรมให้ตรงกับที่เลือก
        config.SYMBOL = symbol
        config.TIMEFRAME_STR = timeframe
        
        bot = TradingBot()
        bot.symbol = symbol
        bot.timeframe = timeframe
        bot.set_socketio(socketio)
        bot.start()
        
    return jsonify({"success": True, "message": f"เริ่มระบบบอทเทรดเรียบร้อย (สแกน {symbol} - {timeframe})"})

@app.route('/api/bot/stop', methods=['POST'])
def bot_stop():
    global bot
    with bot_lock:
        if bot and bot.is_alive() and bot.is_running():
            bot.stop()
            # รอสักครู่ให้เทรดจบ
            bot.join(timeout=2)
            return jsonify({"success": True, "message": "ส่งคำสั่งหยุดการรันของบอทแล้ว"})
    return jsonify({"success": True, "message": "บอทไม่ได้ทำงานอยู่"})

@app.route('/api/bot/status', methods=['GET'])
def bot_status():
    global bot
    is_running = bot.is_running() if bot and bot.is_alive() else False
    current_symbol = bot.symbol if bot else config.SYMBOL
    current_timeframe = bot.timeframe if bot else config.TIMEFRAME_STR
    return jsonify({
        "running": is_running,
        "symbol": current_symbol,
        "timeframe": current_timeframe
    })

@app.route('/api/bot/analyze-now', methods=['POST'])
def bot_analyze_now():
    current_bot = get_or_create_bot()
    
    # รันวิเคราะห์นอกรอบใน Background
    def run_now():
        current_bot.log_message("⚡ [Manual Trigger] เริ่มต้นรอบการวิเคราะห์ตลาดทันทีตามคำสั่ง...")
        current_bot.run_single_cycle()
        
    t = threading.Thread(target=run_now)
    t.start()
    return jsonify({"success": True, "message": "กำลังสั่งให้บอทวิเคราะห์ตลาดทันที..."})

@app.route('/api/learning/notes', methods=['GET'])
def get_learning_notes():
    note = database.get_latest_learning_note()
    return jsonify(note or {"notes": "ยังไม่มีประวัติการเรียนรู้", "timestamp": "-"})

@app.route('/api/learning/generate', methods=['POST'])
def generate_learning():
    current_bot = get_or_create_bot()
    closed_trades = [t for t in database.get_recent_trades(limit=10) if t['status'] == 'CLOSED']
    if not closed_trades:
        return jsonify({"success": False, "message": "ยังไม่มีผลการเทรดที่ปิดแล้วในการวิเคราะห์"})
        
    def run_learning():
        current_bot.log_message("🧠 [Manual Trigger] กำลังวิเคราะห์ผลเพื่อสร้าง Learning Notes ด้วย AI...")
        notes = current_bot.analyst.generate_learning_summary(closed_trades)
        database.save_learning_note(notes, len(closed_trades))
        current_bot.log_message("✅ AI สร้าง Learning Notes จากระบบ Manual สำเร็จ!")
        socketio.emit('learning_update', {'notes': notes})
        
    t = threading.Thread(target=run_learning)
    t.start()
    return jsonify({"success": True, "message": "กำลังสร้างรายงานผลการเทรดด้วย AI..."})

if __name__ == '__main__':
    # สั่งสร้างฐานข้อมูล SQLite
    database.init_db()
    
    # รันเว็บเซิร์ฟเวอร์
    port = config.FLASK_PORT
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
