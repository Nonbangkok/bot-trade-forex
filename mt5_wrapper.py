import sys
import time
import random
import numpy as np

# กำหนดสัญลักษณ์ค่าคงที่ของ Timeframe ให้ตรงกับ MT5 ของจริง
TIMEFRAME_M15 = 15
TIMEFRAME_H1 = 16385
TIMEFRAME_H4 = 16388
TIMEFRAME_D1 = 16408

# Order Type Constants
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1

# Action Constants
TRADE_ACTION_DEAL = 1

# Filling Constants
ORDER_FILLING_IOC = 1
ORDER_FILLING_FOK = 0
ORDER_FILLING_RETURN = 2

# Result Codes
TRADE_RETCODE_DONE = 10009

# ตรวจสอบระบบปฏิบัติการว่าเป็น Windows หรือไม่
IS_WINDOWS = sys.platform.startswith("win")

class MockPosition:
    def __init__(self, ticket, symbol, type_val, volume, price_open, sl, tp, comment):
        self.ticket = ticket
        self.symbol = symbol
        self.type = type_val # 0 = BUY, 1 = SELL
        self.volume = volume
        self.price_open = price_open
        self.sl = sl
        self.tp = tp
        self.price_current = price_open
        self.profit = 0.0
        self.comment = comment
        self.time = int(time.time())

class MockMT5:
    TIMEFRAME_M15 = TIMEFRAME_M15
    TIMEFRAME_H1 = TIMEFRAME_H1
    TIMEFRAME_H4 = TIMEFRAME_H4
    TIMEFRAME_D1 = TIMEFRAME_D1

    # Order Type Constants
    ORDER_TYPE_BUY = ORDER_TYPE_BUY
    ORDER_TYPE_SELL = ORDER_TYPE_SELL
    
    # Action Constants
    TRADE_ACTION_DEAL = TRADE_ACTION_DEAL
    
    # Filling Constants
    ORDER_FILLING_IOC = ORDER_FILLING_IOC
    ORDER_FILLING_FOK = ORDER_FILLING_FOK
    ORDER_FILLING_RETURN = ORDER_FILLING_RETURN

    # Result Codes
    TRADE_RETCODE_DONE = TRADE_RETCODE_DONE
    
    def __init__(self):
        print("\n" + "="*50)
        print("🤖 RUNNING IN MOCK MODE (NON-WINDOWS PLATFORM)")
        print("All MetaTrader 5 API calls will be simulated.")
        print("="*50 + "\n")
        
        self.login_id = 9999999
        self.server_name = "MockServer-Demo"
        self._positions = []
        self._ticket_counter = 50000000
        
        # ราคาตั้งต้นและราคาปัจจุบัน
        self._base_prices = {
            "EURUSD": 1.08200,
            "GBPUSD": 1.27300,
            "XAUUSD": 2350.00
        }
        self._current_prices = dict(self._base_prices)

    def initialize(self, *args, **kwargs):
        print("[MOCK MT5] Initialized connection to simulated MetaTrader 5 terminal.")
        return True

    def shutdown(self):
        print("[MOCK MT5] Shutdown connection.")
        return None

    class MockAccountInfo:
        def __init__(self, login, balance, equity, margin_free):
            self.login = login
            self.balance = balance
            self.equity = equity
            self.margin_free = margin_free
            self.currency = "USD"
            self.leverage = 500

    def account_info(self):
        # คำนวณบาลานซ์และเอคิวตี้จำลอง (หัก/บวกกำไรของออเดอร์ที่ค้างอยู่)
        open_profit = sum(p.profit for p in self._positions)
        balance = 10000.00
        # สมมุติว่าบาลานซ์ลดลงตามการปิดออเดอร์ แต่ในการจำลองให้บาลานซ์คงเดิมและเอคิวตี้เปลี่ยนตามกำไรค้างอยู่
        equity = balance + open_profit
        margin_free = equity - sum(p.volume * 200 for p in self._positions) # จำลองมาร์จิ้น
        
        return self.MockAccountInfo(self.login_id, balance, equity, margin_free)

    class MockSymbolInfo:
        def __init__(self, symbol, current_price):
            self.name = symbol
            self.digits = 3 if "JPY" in symbol or "XAU" in symbol else 5
            self.spread = 15
            self.point = 0.1 if "XAU" in symbol else (0.01 if "JPY" in symbol else 0.00001)
            self.trade_tick_size = self.point
            
            # Bid/Ask
            self.bid = current_price
            self.ask = current_price + (self.spread * self.point)
            self.filling_mode = 3 # FOK + IOC

    def symbol_info(self, symbol):
        price = self._current_prices.get(symbol, 1.00000)
        return self.MockSymbolInfo(symbol, price)

    class MockTick:
        def __init__(self, symbol, bid, ask):
            self.time = int(time.time())
            self.bid = bid
            self.ask = ask
            self.last = bid
            self.volume = 0

    def symbol_info_tick(self, symbol):
        # อัปเดตราคาแบบสุ่มเล็กน้อย (สร้าง tick เคลื่อนไหว)
        if symbol in self._current_prices:
            change_pips = random.uniform(-3, 3)
            sym_info = self.symbol_info(symbol)
            point = sym_info.point
            self._current_prices[symbol] += change_pips * point
            
        # ดึงราคาปัจจุบันใหม่
        price = self._current_prices.get(symbol, 1.00000)
        sym_info = self.symbol_info(symbol)
        
        # ตรวจสอบและปิดโพซิชั่นจำลองถ้าชน TP/SL
        self._check_mock_sl_tp(symbol, price, sym_info.point)
        
        return self.MockTick(symbol, sym_info.bid, sym_info.ask)

    def _check_mock_sl_tp(self, symbol, current_price, point):
        """ตรวจสอบ SL/TP ของโพซิชั่นจำลองและปิดออเดอร์"""
        active_pos = []
        for pos in self._positions:
            if pos.symbol != symbol:
                active_pos.append(pos)
                continue
                
            # คำนวณกำไรค้าง ณ ราคาปัจจุบัน
            # EURUSD / GBPUSD point = 0.00001 (1 pip = 10 points หรือ 0.00010)
            # กำไร = (Current - Entry) * Lot * 100000
            # XAUUSD point = 0.1 หรือ 0.01 (กำไร = (Current - Entry) * Lot * 100)
            pip_mult = 100000 if "XAU" not in symbol else 100
            
            if pos.type == ORDER_TYPE_BUY:
                pos.price_current = current_price
                pos.profit = (current_price - pos.price_open) * pip_mult * pos.volume
                
                # เช็ค SL / TP
                if pos.sl and current_price <= pos.sl:
                    print(f"[MOCK MT5] BUY Position Ticket {pos.ticket} hit Stop Loss at {current_price}")
                elif pos.tp and current_price >= pos.tp:
                    print(f"[MOCK MT5] BUY Position Ticket {pos.ticket} hit Take Profit at {current_price}")
                else:
                    active_pos.append(pos)
            else: # SELL
                # โพซิชั่น SELL ปิดที่ราคา Ask ดังนั้นใช้ราคา Bid + spread
                ask_price = current_price + (15 * point)
                pos.price_current = ask_price
                pos.profit = (pos.price_open - ask_price) * pip_mult * pos.volume
                
                # เช็ค SL / TP
                if pos.sl and ask_price >= pos.sl:
                    print(f"[MOCK MT5] SELL Position Ticket {pos.ticket} hit Stop Loss at {ask_price}")
                elif pos.tp and ask_price <= pos.tp:
                    print(f"[MOCK MT5] SELL Position Ticket {pos.ticket} hit Take Profit at {ask_price}")
                else:
                    active_pos.append(pos)
                    
        self._positions = active_pos

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        """จำลองราคาย้อนหลังแท่งเทียน"""
        dtype = [
            ('time', 'i8'),
            ('open', 'f8'),
            ('high', 'f8'),
            ('low', 'f8'),
            ('close', 'f8'),
            ('tick_volume', 'i8'),
            ('spread', 'i4'),
            ('real_volume', 'i8')
        ]
        
        rates = np.zeros(count, dtype=dtype)
        current_time = int(time.time())
        time_step = 14400 if timeframe == TIMEFRAME_H4 else (3600 if timeframe == TIMEFRAME_H1 else 900)
        
        base_price = self._current_prices.get(symbol, 1.08200)
        # จำลองการเทรนขาขึ้นเบาๆ
        for i in range(count):
            offset = (i - count / 2) * 0.00010
            noise = np.sin(i * 0.2) * 0.00080 + offset
            rates[i]['time'] = current_time - (count - 1 - i) * time_step
            rates[i]['open'] = base_price + noise - 0.00010
            rates[i]['high'] = base_price + noise + 0.00040
            rates[i]['low'] = base_price + noise - 0.00030
            rates[i]['close'] = base_price + noise
            rates[i]['tick_volume'] = 1000 + int(random.random() * 800)
            rates[i]['spread'] = 15
            rates[i]['real_volume'] = 0
            
        return rates

    class MockOrderResult:
        def __init__(self, request, ticket):
            self.retcode = TRADE_RETCODE_DONE
            self.order = ticket
            self.volume = request.get('volume', 0.01)
            self.price = request.get('price', 1.08250)
            self.comment = request.get('comment', 'Mock')
            self.request = request

    def order_send(self, request):
        action_type = "BUY" if request.get('type') == self.ORDER_TYPE_BUY else "SELL"
        ticket = self._ticket_counter
        self._ticket_counter += 1
        
        if request.get('action') == self.TRADE_ACTION_DEAL:
            pos = MockPosition(
                ticket=ticket,
                symbol=request.get('symbol'),
                type_val=request.get('type'),
                volume=request.get('volume'),
                price_open=request.get('price'),
                sl=request.get('sl'),
                tp=request.get('tp'),
                comment=request.get('comment')
            )
            self._positions.append(pos)
            
        print("\n" + "🔔" + "-"*40)
        print("📝 [MOCK ORDER EXECUTION]")
        print(f"Action:     {action_type}")
        print(f"Symbol:     {request.get('symbol')}")
        print(f"Volume:     {request.get('volume')} Lots")
        print(f"Price:      {request.get('price')}")
        print(f"Stop Loss:  {request.get('sl')}")
        print(f"Take Profit:{request.get('tp')}")
        print(f"Ticket ID:  {ticket}")
        print("-"*42 + "\n")
        
        return self.MockOrderResult(request, ticket)

    def positions_get(self, symbol=None, **kwargs):
        if symbol:
            return tuple(p for p in self._positions if p.symbol == symbol)
        return tuple(self._positions)

# โหลดโมดูลจริงหรือจำลองตามระบบปฏิบัติการ
if IS_WINDOWS:
    try:
        import MetaTrader5 as _mt5_real
        print("[MT5 Wrapper] Successfully imported real MetaTrader5 library.")
    except ImportError:
        print("[MT5 Wrapper] ERROR: Running on Windows but 'MetaTrader5' library is not installed.")
        print("[MT5 Wrapper] Please run: pip install MetaTrader5")
        sys.exit(1)

    class _RealMT5Wrapper:
        """Wraps the real MetaTrader5 module so that initialize() always
        re-uses stored credentials — fixing reconnection after shutdown()."""
        IS_WINDOWS = True
        _login = None
        _password = None
        _server = None

        def initialize(self, *args, **kwargs):
            # If called with no arguments, inject stored credentials
            if not args and not kwargs and self._login is not None:
                return _mt5_real.initialize(
                    login=self._login,
                    password=self._password,
                    server=self._server
                )
            return _mt5_real.initialize(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(_mt5_real, name)

    mt5 = _RealMT5Wrapper()
else:
    # ใช้งานคลาสจำลองสำหรับ macOS
    mt5 = MockMT5()

# ==========================================
# Module Helper Functions for Integration
# ==========================================

def initialize_with_login(server, login, password):
    """
    เชื่อมต่อ MT5 ด้วยระบบบัญชี
    """
    if not IS_WINDOWS:
        print(f"[MOCK MT5] Logged in with Account: {login} on Server: {server}")
        mt5.login_id = int(login)
        mt5.server_name = server
        return True

    try:
        login_int = int(login)
    except ValueError:
        print("[MT5 Wrapper] Invalid Login ID (must be integer)")
        return False

    # Store credentials so every future initialize() call reuses them
    mt5._login = login_int
    mt5._password = password
    mt5._server = server

    # ล็อกอินจริงบนระบบ Windows
    if not _mt5_real.initialize(login=login_int, password=password, server=server):
        print(f"[MT5 Wrapper] Failed to initialize MT5 login: {_mt5_real.last_error()}")
        return False

    return True

def get_account_summary():
    """
    ดึงข้อมูลบาลานซ์และสถานะการลงทุนปัจจุบัน
    """
    mt5.initialize()  # re-uses stored credentials on Windows; no-op on mock
    acc = mt5.account_info()
    mt5.shutdown()
    if acc is None:
        return {
            "login": 0,
            "balance": 0.0,
            "equity": 0.0,
            "margin_free": 0.0,
            "currency": "USD",
            "server": "Offline",
            "connected": False
        }
        
    # ดึงค่า Server จาก Mock หรือจากระบบ MT5 จริง
    server = getattr(mt5, 'server_name', 'MetaQuotes-Demo')
    if IS_WINDOWS:
        # ดึงจากโครงสร้าง MT5 account_info
        server = getattr(acc, 'server', 'MetaQuotes-Demo')
        
    return {
        "login": acc.login,
        "balance": round(acc.balance, 2),
        "equity": round(acc.equity, 2),
        "margin_free": round(acc.margin_free, 2),
        "currency": getattr(acc, "currency", "USD"),
        "server": server,
        "connected": True
    }
