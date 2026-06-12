import requests
import json
import logging
from config import MAXPLUS_API_KEY, MAXPLUS_BASE_URL, MODEL_NAME

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class AIAnalyst:
    def __init__(self):
        self.api_key = MAXPLUS_API_KEY
        self.base_url = MAXPLUS_BASE_URL
        self.model = MODEL_NAME
        
        # ตรวจสอบรูปแบบคีย์เบื้องต้น
        if not self.api_key or self.api_key == "ccsk-YOUR_API_KEY_HERE":
            logging.warning("⚠️ API Key ยังไม่ได้รับการตั้งค่า! กรุณาแก้ไขในไฟล์ .env")

    def analyze_market(self, symbol, timeframe, current_price, current_spread, df_candles):
        """
        เตรียมข้อมูลวิเคราะห์ตลาด สร้าง Prompt ส่งหา MaxPlus AI 
        และรับผลลัพธ์การแนะนำเทรดเป็น JSON
        """
        # 1. แปลงตารางแท่งเทียนให้เป็นข้อความสรุปสำหรับป้อนลง Prompt
        candles_summary = []
        # เรียงลำดับจากอดีต -> แท่งปัจจุบัน (เพื่อประหยัด Token ดึงเฉพาะแท่งเทียนล่าสุด 10-15 แท่งก็พอ)
        recent_candles = df_candles.tail(15)
        for idx, row in recent_candles.iterrows():
            candles_summary.append(
                f"Time: {row['time_str']} | O: {row['open']:.5f} | H: {row['high']:.5f} | L: {row['low']:.5f} | C: {row['close']:.5f} | RSI: {row['rsi']:.2f} | MA_Fast: {row['ma_fast']:.5f} | MA_Slow: {row['ma_slow']:.5f}"
            )
        
        candles_text = "\n".join(candles_summary)

        # 2. ออกแบบ System Prompt และ User Prompt
        system_prompt = (
            "You are an expert Forex trader and quantitative research analyst.\n"
            "Analyze the given market candlestick data along with Technical Indicators (RSI, EMAs).\n"
            "Provide a logical trade analysis and decide on a recommendation: BUY, SELL, or HOLD.\n"
            "You must return the output STRICTLY as a JSON object with the following fields:\n"
            "{\n"
            '  "recommendation": "BUY" | "SELL" | "HOLD",\n'
            '  "sl_pips": <float or null for HOLD>,\n'
            '  "tp_pips": <float or null for HOLD>,\n'
            '  "reasoning": "<string summarizing your technical analysis and why you made this decision>"\n'
            "}\n"
            "Rules:\n"
            "1. Recommend BUY or SELL only if there is a high-probability trade setup. Otherwise, recommend HOLD.\n"
            "2. 'sl_pips' and 'tp_pips' must be represented in pips (1 pip = 0.00010 for EURUSD/GBPUSD, 0.01 for XAUUSD).\n"
            "3. Ensure the risk-to-reward ratio is at least 1:1.5.\n"
            "4. Do NOT output any explanation text outside the JSON object. Output raw JSON only."
        )

        user_content = (
            f"Market Data:\n"
            f"Symbol: {symbol}\n"
            f"Timeframe: {timeframe}\n"
            f"Current Price (Bid/Ask): {current_price['bid']:.5f} / {current_price['ask']:.5f}\n"
            f"Current Spread: {current_spread} points\n\n"
            f"Recent Candlestick Data:\n"
            f"{candles_text}\n"
        )

        # 3. ยิง HTTP POST ไปที่ MaxPlus AI API
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            # บังคับผลลัพธ์ให้ออกมาเป็น JSON
            "response_format": {"type": "json_object"}
        }

        try:
            logging.info(f"📤 Sending request to MaxPlus AI using model: {self.model}...")
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            # ตรวจสอบ HTTP Status
            if response.status_code == 402:
                logging.error("❌ Insufficient Credit (402): กรุณาเติมเงินในบัญชี MaxPlus AI ของคุณ")
                return {"recommendation": "HOLD", "reasoning": "Error: Insufficient Credit on MaxPlus AI"}
            elif response.status_code != 200:
                logging.error(f"❌ API Error ({response.status_code}): {response.text}")
                return {"recommendation": "HOLD", "reasoning": f"Error: API returned status {response.status_code}"}

            # 4. แกะ JSON ผลลัพธ์
            resp_data = response.json()
            content_str = resp_data["choices"][0]["message"]["content"]
            
            # แปลงข้อความเป็น Python dictionary
            decision = json.loads(content_str)
            logging.info("📥 Successfully received and parsed trade decision.")
            logging.info(f"AI Decision: {decision.get('recommendation')} | Reason: {decision.get('reasoning')}")
            
            return decision

        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Network request failed: {e}")
            return {"recommendation": "HOLD", "reasoning": f"Error: Network connection failed: {e}"}
        except json.JSONDecodeError as e:
            logging.error(f"❌ Failed to decode JSON response from AI: {e}")
            logging.error(f"Raw Content: {content_str if 'content_str' in locals() else 'None'}")
            return {"recommendation": "HOLD", "reasoning": "Error: AI response could not be decoded to JSON"}
        except Exception as e:
            logging.error(f"❌ Unexpected error in AI Analyst: {e}")
            return {"recommendation": "HOLD", "reasoning": f"Error: Unexpected error: {e}"}
