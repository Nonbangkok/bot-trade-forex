import sqlite3
import os
import logging
from datetime import datetime

DB_NAME = "trade_journal.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """สร้างตารางในฐานข้อมูลหากยังไม่มี"""
    logging.info("Initializing SQLite database...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # ตาราง trades
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER UNIQUE,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            entry_price REAL NOT NULL,
            sl REAL,
            tp REAL,
            lot_size REAL NOT NULL,
            confidence INTEGER,
            reasoning TEXT,
            status TEXT DEFAULT 'OPEN'
        )
    """)
    
    # ตาราง trade_results
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER UNIQUE NOT NULL,
            exit_price REAL NOT NULL,
            pnl_pips REAL NOT NULL,
            pnl_usd REAL NOT NULL,
            duration INTEGER, -- duration in seconds
            outcome TEXT NOT NULL, -- 'WIN', 'LOSS', 'BE'
            timestamp TEXT NOT NULL,
            FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE
        )
    """)
    
    # ตาราง ai_learning_notes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_learning_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            notes TEXT NOT NULL,
            order_count_analyzed INTEGER NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully.")

def save_trade(ticket_id, symbol, action, entry_price, sl, tp, lot_size, confidence, reasoning, status="OPEN"):
    """บันทึกออเดอร์เปิดใหม่ลงฐานข้อมูล และส่งกลับไอดีแถว"""
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        INSERT INTO trades (ticket_id, timestamp, symbol, action, entry_price, sl, tp, lot_size, confidence, reasoning, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticket_id, timestamp, symbol, action, entry_price, sl, tp, lot_size, confidence, reasoning, status))
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return trade_id

def update_trade_result(trade_id, exit_price, pnl_pips, pnl_usd, duration, outcome):
    """อัปเดตผลลัพธ์การปิดออเดอร์"""
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        # อัปเดตสถานะในตาราง trades
        cursor.execute("UPDATE trades SET status = 'CLOSED' WHERE id = ?", (trade_id,))
        
        # เพิ่มข้อมูลผลลัพธ์ในตาราง trade_results
        cursor.execute("""
            INSERT OR REPLACE INTO trade_results (trade_id, exit_price, pnl_pips, pnl_usd, duration, outcome, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (trade_id, exit_price, pnl_pips, pnl_usd, duration, outcome, timestamp))
        
        conn.commit()
        logging.info(f"Updated trade ID {trade_id} result in database. P&L: {pnl_usd} USD")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error updating trade result in database: {e}")
    finally:
        conn.close()

def get_open_trades():
    """ดึงรายการออเดอร์ที่ยังเปิดค้างอยู่"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE status = 'OPEN' ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_recent_trades(limit=50):
    """ดึงข้อมูลรายการเทรดล่าสุดทั้งหมด พร้อมผลลัพธ์ (ถ้าปิดแล้ว)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.id, t.ticket_id, t.timestamp, t.symbol, t.action, t.entry_price, t.sl, t.tp, t.lot_size, 
               t.confidence, t.reasoning, t.status,
               r.exit_price, r.pnl_pips, r.pnl_usd, r.duration, r.outcome, r.timestamp as close_timestamp
        FROM trades t
        LEFT JOIN trade_results r ON t.id = r.trade_id
        ORDER BY t.id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_performance_stats():
    """คำนวณและแสดงสถิติผลงานเทรดทั้งหมด"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # จำนวนเทรดทั้งหมด
    cursor.execute("SELECT COUNT(*) FROM trades")
    total_trades = cursor.fetchone()[0]
    
    # จำนวนเทรดที่ปิดแล้ว
    cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED'")
    closed_trades = cursor.fetchone()[0]
    
    # ชนะ แพ้ เสมอตัว
    cursor.execute("SELECT outcome, COUNT(*) FROM trade_results GROUP BY outcome")
    outcome_counts = dict(cursor.fetchall())
    wins = outcome_counts.get('WIN', 0)
    losses = outcome_counts.get('LOSS', 0)
    bes = outcome_counts.get('BE', 0)
    
    # Win Rate (%)
    win_rate = (wins / closed_trades * 100) if closed_trades > 0 else 0
    
    # รวมกำไร/ขาดทุน
    cursor.execute("SELECT SUM(pnl_usd), SUM(pnl_pips) FROM trade_results")
    res = cursor.fetchone()
    total_pnl_usd = res[0] if res and res[0] is not None else 0.0
    total_pnl_pips = res[1] if res and res[1] is not None else 0.0
    
    # หาค่า Risk to Reward เฉลี่ย
    # (คำนวณจากการเอา TP / SL ของออเดอร์ที่ตั้งไว้)
    cursor.execute("SELECT sl, tp, entry_price, action FROM trades WHERE sl IS NOT NULL AND tp IS NOT NULL AND status = 'CLOSED'")
    rr_ratios = []
    for sl, tp, entry, action in cursor.fetchall():
        try:
            if action == 'BUY':
                risk = entry - sl
                reward = tp - entry
            else:
                risk = sl - entry
                reward = entry - tp
            if risk > 0:
                rr_ratios.append(reward / risk)
        except Exception:
            continue
    avg_rr = sum(rr_ratios) / len(rr_ratios) if rr_ratios else 0.0
    
    conn.close()
    
    return {
        "total_trades": total_trades,
        "closed_trades": closed_trades,
        "wins": wins,
        "losses": losses,
        "be": bes,
        "win_rate": round(win_rate, 2),
        "total_pnl_usd": round(total_pnl_usd, 2),
        "total_pnl_pips": round(total_pnl_pips, 2),
        "avg_rr": round(avg_rr, 2)
    }

def save_learning_note(notes, order_count_analyzed):
    """บันทึกโน้ตการเรียนรู้ของ AI"""
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        INSERT INTO ai_learning_notes (timestamp, notes, order_count_analyzed)
        VALUES (?, ?, ?)
    """, (timestamp, notes, order_count_analyzed))
    conn.commit()
    conn.close()

def get_latest_learning_note():
    """ดึงโน้ตการเรียนรู้ล่าสุดของ AI"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_learning_notes ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# สั่งทดสอบการทำงานเบื้องต้น
if __name__ == "__main__":
    init_db()
    print("Database init test completed.")
