import sys
import time
import numpy as np

# กำหนดสัญลักษณ์ค่าคงที่ของ Timeframe ให้ตรงกับ MT5 ของจริง
TIMEFRAME_M15 = 15
TIMEFRAME_H1 = 16385
TIMEFRAME_H4 = 16388
TIMEFRAME_D1 = 16408

# ตรวจสอบระบบปฏิบัติการว่าเป็น Windows หรือไม่
IS_WINDOWS = sys.platform.startswith("win")

# คลาสจำลองสำหรับ macOS
class MockMT5:
    TIMEFRAME_M15 = TIMEFRAME_M15
    TIMEFRAME_H1 = TIMEFRAME_H1
    TIMEFRAME_H4 = TIMEFRAME_H4
    TIMEFRAME_D1 = TIMEFRAME_D1

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
    
    def __init__(self):
        print("\n" + "="*50)
        print("🤖 RUNNING IN MOCK MODE (NON-WINDOWS PLATFORM)")
        print("All MetaTrader 5 API calls will be simulated.")
        print("="*50 + "\n")

    def initialize(self, *args, **kwargs):
        print("[MOCK MT5] Initialized connection to simulated MetaTrader 5 terminal.")
        return True

    def shutdown(self):
        print("[MOCK MT5] Shutdown connection.")
        return None

    class MockAccountInfo:
        def __init__(self):
            self.login = 9999999
            self.balance = 10000.00
            self.equity = 10000.00
            self.margin_free = 10000.00
            self.currency = "USD"
            self.leverage = 500

    def account_info(self):
        return self.MockAccountInfo()

    class MockSymbolInfo:
        def __init__(self, symbol):
            self.name = symbol
            self.digits = 5
            self.spread = 15
            self.ask = 1.08250
            self.bid = 1.08235
            self.trade_tick_size = 0.00001
            self.point = 0.00001

    def symbol_info(self, symbol):
        return self.MockSymbolInfo(symbol)

    class MockTick:
        def __init__(self, symbol):
            self.time = int(time.time())
            self.bid = 1.08235
            self.ask = 1.08250
            self.last = 1.08235
            self.volume = 0

    def symbol_info_tick(self, symbol):
        return self.MockTick(symbol)

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        """
        จำลองประวัติราคาย้อนหลัง (Candlestick data) 
        และสร้างแนวโน้มราคาให้จำลองการคำนวณอินดิเคเตอร์ได้สมจริง
        """
        # สร้าง numpy structured array เลียนแบบโครงสร้าง MT5
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
        time_step = 14400 if timeframe == TIMEFRAME_H4 else 3600 # H4 or H1 in seconds
        
        # จำลองราคาแกว่งขึ้นเล็กน้อย (Uptrend) เพื่อคำนวณอินดิเคเตอร์ได้สวยๆ
        base_price = 1.08000
        for i in range(count):
            # i = 0 คือแท่งเทียนอดีตสุด, i = count-1 คือแท่งเทียนปัจจุบัน
            # สร้างการแกว่งตัวของราคาแบบสุ่ม
            noise = np.sin(i * 0.5) * 0.00100 + (i * 0.00010)
            rates[i]['time'] = current_time - (count - 1 - i) * time_step
            rates[i]['open'] = base_price + noise
            rates[i]['high'] = base_price + noise + 0.00050
            rates[i]['low'] = base_price + noise - 0.00030
            rates[i]['close'] = base_price + noise + 0.00020
            rates[i]['tick_volume'] = 1500 + int(noise * 10000)
            rates[i]['spread'] = 15
            rates[i]['real_volume'] = 0
            
        return rates

    class MockOrderResult:
        def __init__(self, request):
            self.retcode = 10009 # TRADE_RETCODE_DONE
            self.order = 12345678 # Mock order ID
            self.volume = request.get('volume', 0.01)
            self.price = request.get('price', 1.08250)
            self.comment = "Mock Execution"
            self.request = request

    def order_send(self, request):
        print("\n" + "🔔" + "-"*40)
        print("📝 [MOCK ORDER EXECUTION]")
        action_type = "BUY" if request.get('type') == self.ORDER_TYPE_BUY else "SELL"
        print(f"Action:     {action_type}")
        print(f"Symbol:     {request.get('symbol')}")
        print(f"Volume:     {request.get('volume')} Lots")
        print(f"Price:      {request.get('price')}")
        print(f"Stop Loss:  {request.get('sl')}")
        print(f"Take Profit:{request.get('tp')}")
        print(f"Comment:    {request.get('comment')}")
        print("-"*42 + "\n")
        return self.MockOrderResult(request)

    def positions_get(self, *args, **kwargs):
        # จำลองว่าไม่มีออเดอร์ค้างอยู่
        return ()

# โหลดโมดูลจริงหรือจำลองตามระบบปฏิบัติการ
if IS_WINDOWS:
    try:
        import MetaTrader5 as mt5
        print("[MT5 Wrapper] Successfully imported real MetaTrader5 library.")
    except ImportError:
        print("[MT5 Wrapper] ERROR: Running on Windows but 'MetaTrader5' library is not installed.")
        print("[MT5 Wrapper] Please run: pip install MetaTrader5")
        sys.exit(1)
else:
    # ใช้งานคลาสจำลองสำหรับ macOS
    mt5 = MockMT5()
