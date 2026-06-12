# MetaTrader 5 Forex Trading Bot (MaxPlus AI)

บอทเทรด Forex บน MetaTrader 5 (MT5) โดยการวิเคราะห์อินดิเคเตอร์ทางเทคนิค (RSI, EMAs) ร่วมกับข้อมูลแท่งเทียนล่าสุด ส่งสัญญาณให้ LLM (เช่น GPT-4o, Claude) ตัดสินใจผ่าน MaxPlus AI API พร้อมระบบสั่งเปิดออเดอร์ (BUY/SELL) ตั้งค่า Stop Loss (SL) และ Take Profit (TP) แบบอัตโนมัติ

โปรเจกต์นี้ได้รับการพัฒนาให้รองรับ **Cross-Platform**:
*   **macOS / Linux:** ทำงานในโหมดจำลอง (Mock Mode) เพื่อใช้พัฒนา ดึงข้อมูลประมวลผล และวิเคราะห์ Prompt ร่วมกับ MaxPlus AI ได้โดยไม่ต้องมีโปรแกรม MT5 ติดตั้งจริงในเครื่อง
*   **Windows:** เชื่อมต่อและส่งคำสั่งเทรดเข้า MT5 Terminal ของจริงโดยอัตโนมัติ

---

## สารบัญไฟล์ในโปรเจกต์

1.  [`config.py`](file:///Users/nonbangkok/Documents/Workspace/Project/bot-trade-forex/config.py): ไฟล์ตั้งค่า API Key, คู่เงินที่เทรด, ขนาดสัญญา (Lot), ค่าคงที่สำหรับอินดิเคเตอร์ และสวิตช์ Auto-Trade
2.  [`mt5_wrapper.py`](file:///Users/nonbangkok/Documents/Workspace/Project/bot-trade-forex/mt5_wrapper.py): ตัวกลางตรวจสอบ OS และสลับการทำงานระหว่าง `MetaTrader5` ของจริง (Windows) และ Mock Class (macOS)
3.  [`ai_analyst.py`](file:///Users/nonbangkok/Documents/Workspace/Project/bot-trade-forex/ai_analyst.py): ส่วนจัดการส่ง Prompt ไปวิเคราะห์กับ MaxPlus AI และแปลงผลลัพธ์ JSON
4.  [`main.py`](file:///Users/nonbangkok/Documents/Workspace/Project/bot-trade-forex/main.py): สคริปต์หลักในการทำงาน
5.  [`.env`](file:///Users/nonbangkok/Documents/Workspace/Project/bot-trade-forex/.env): ไฟล์เก็บรักษารหัส API Key และพารามิเตอร์ที่เป็นความลับ

---

## ขั้นตอนการติดตั้งและใช้งาน

### 1. การติดตั้งในฝั่ง Development (macOS)
1.  ติดตั้งไลบรารีที่จำเป็น (ไม่รวม `MetaTrader5` เนื่องจากไม่รองรับ macOS):
    ```bash
    pip install -r requirements.txt
    ```
2.  สร้างคีย์ API ที่ [MaxPlus AI Dashboard](https://maxplus-ai.cc/dashboard) (คีย์ขึ้นต้นด้วย `ccsk-...`)
3.  เปิดไฟล์ [`.env`](file:///Users/nonbangkok/Documents/Workspace/Project/bot-trade-forex/.env) และแก้ไขคีย์ในช่อง `MAXPLUS_API_KEY`:
    ```env
    MAXPLUS_API_KEY=ccsk-คีย์ของคุณตรงนี้
    ```
4.  รันบอททดสอบเพื่อดูการวิเคราะห์ผ่าน Mock Mode:
    ```bash
    python main.py
    ```

### 2. การนำไปใช้งานจริงบน Windows (Production)
1.  ตรวจสอบว่าในเครื่อง Windows ของคุณมีโปรแกรม **MetaTrader 5 (MT5)** ติดตั้งและเปิดใช้งานอยู่ พร้อมทั้งล็อกอินบัญชีเทรด (แนะนำบัญชี Demo ก่อน) เรียบร้อยแล้ว
2.  ติดตั้ง Python และไลบรารีสำหรับ Windows:
    ```bash
    pip install -r requirements.txt
    pip install MetaTrader5
    ```
3.  คัดลอกไฟล์โปรเจกต์ทั้งหมด (รวมถึงไฟล์ `.env` ที่ใส่ API Key แล้ว) ไปยังเครื่อง Windows
4.  เปิดไฟล์ [`.env`](file:///Users/nonbangkok/Documents/Workspace/Project/bot-trade-forex/.env) เพื่อเปิดระบบยิงออเดอร์จริง:
    ```env
    AUTO_TRADE=True
    ```
5.  รันบอทหลัก:
    ```bash
    python main.py
    ```

---

## ข้อควรระวัง & คำแนะนำด้านความปลอดภัย
*   **AUTO_TRADE:** ในไฟล์ `.env` หากตั้งเป็น `False` บอทจะทำการดึงราคา วิเคราะห์ และพิมพ์คำแนะนำจาก AI ลงใน Log เท่านั้นโดยจะยังไม่สั่งเปิดออเดอร์จริง เหมาะสำหรับใช้ทดสอบการทำงานระยะยาว
*   **Demo Account:** ขอแนะนำเป็นอย่างยิ่งให้ทดสอบการทำงานของบอทด้วยบัญชีทดลอง (Demo Account) บน MT5 ก่อนอย่างน้อย 1-2 สัปดาห์ เพื่อดูความสอดคล้องของการส่งออเดอร์และระบบ Risk Management ก่อนตัดสินใจรันบนบัญชีเงินจริง
