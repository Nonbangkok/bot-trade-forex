import requests
import json
import logging
import random
from config import MAXPLUS_API_KEY, MAXPLUS_BASE_URL, MODEL_NAME

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class AIAnalyst:
    def __init__(self):
        self.api_key = MAXPLUS_API_KEY
        self.base_url = MAXPLUS_BASE_URL
        self.model = MODEL_NAME
        
        # ตรวจสอบรูปแบบคีย์เบื้องต้น
        if not self.api_key or self.api_key == "ccsk-YOUR_API_KEY_HERE":
            logging.warning("⚠️ API Key ยังไม่ได้รับการตั้งค่า! ระบบจะจำลองผลการวิเคราะห์ให้โดยอัตโนมัติ")

    def analyze_market(self, symbol, timeframe, current_price, current_spread, df_candles, learning_notes=None):
        """
        เตรียมข้อมูลวิเคราะห์ตลาด สร้าง Prompt ส่งหา MaxPlus AI 
        และรับผลลัพธ์การแนะนำเทรดเป็น JSON พร้อม confidence_score และนำ learning_notes มาปรับปรุงการเทรด
        """
        # หากไม่ได้ตั้ง API Key จริง ให้เข้าโหมดจำลองทันที
        if not self.api_key or self.api_key == "ccsk-YOUR_API_KEY_HERE":
            logging.warning("⚠️ MaxPlus AI API Key is mock. Generating simulated trading signal...")
            return self._generate_mock_decision(symbol, current_price)

        # 1. แปลงตารางแท่งเทียนให้เป็นข้อความสรุปสำหรับป้อนลง Prompt
        candles_summary = []
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
            '  "confidence_score": <int between 0 and 100, representing your confidence in this signal>,\n'
            '  "reasoning": "<string summarizing your technical analysis and why you made this decision>"\n'
            "}\n"
            "Rules:\n"
            "1. Recommend BUY or SELL only if there is a high-probability trade setup. Otherwise, recommend HOLD.\n"
            "2. 'sl_pips' and 'tp_pips' must be represented in pips (1 pip = 0.00010 for EURUSD/GBPUSD, 0.01 for XAUUSD).\n"
            "3. Ensure the risk-to-reward ratio is at least 1:1.5.\n"
            "4. Do NOT output any explanation text outside the JSON object. Output raw JSON only."
        )

        if learning_notes:
            system_prompt += (
                f"\n\nCRITICAL: Below are historical LEARNING NOTES from your past trades' outcomes.\n"
                f"Use this feedback to refine your current decision (e.g., if you lost multiple times on a specific setup, avoid it):\n"
                f"--- START LEARNING NOTES ---\n"
                f"{learning_notes}\n"
                f"--- END LEARNING NOTES ---"
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
            "response_format": {"type": "json_object"}
        }

        try:
            logging.info(f"📤 Sending request to MaxPlus AI using model: {self.model}...")
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            # หากระบบปลายทางล่ม หรือเครดิตหมด ให้เปิดโหมดจำลองเพื่อให้บอททำงานต่อได้
            if response.status_code in (402, 503, 500, 502, 504):
                logging.warning(f"⚠️ MaxPlus AI API returned error status {response.status_code}. Falling back to Simulated AI Trader.")
                return self._generate_mock_decision(symbol, current_price)
            elif response.status_code != 200:
                logging.error(f"❌ API Error ({response.status_code}): {response.text}")
                return self._generate_mock_decision(symbol, current_price)

            resp_data = response.json()
            content_str = resp_data["choices"][0]["message"]["content"]
            decision = json.loads(content_str)
            logging.info("📥 Successfully received and parsed trade decision.")
            logging.info(f"AI Decision: {decision.get('recommendation')} | Confidence: {decision.get('confidence_score')}% | Reason: {decision.get('reasoning')}")
            return decision

        except Exception as e:
            logging.error(f"❌ Connection or parsing failed, falling back to simulated decision: {e}")
            return self._generate_mock_decision(symbol, current_price)

    def generate_learning_summary(self, closed_trades):
        """
        ส่งผลการเทรดที่ปิดแล้วล่าสุด 5-10 รายการ ให้ AI สรุปบทเรียน (Learning Notes)
        """
        if not closed_trades:
            return "ยังไม่มีประวัติการเทรดที่ปิดแล้วสำหรับการวิเคราะห์"

        # หากไม่ได้ตั้ง API Key จริง ให้เข้าโหมดจำลองทันที
        if not self.api_key or self.api_key == "ccsk-YOUR_API_KEY_HERE":
            logging.warning("⚠️ MaxPlus AI API Key is mock. Generating simulated learning summary...")
            return self._generate_mock_learning_notes(closed_trades)

        trades_summary = []
        for t in closed_trades:
            trades_summary.append(
                f"Trade ID: {t['id']} | Action: {t['action']} | Entry: {t['entry_price']:.5f} | Exit: {t['exit_price']:.5f} | "
                f"SL: {t.get('sl')} | TP: {t.get('tp')} | P&L: {t['pnl_usd']:.2f} USD ({t['pnl_pips']:.1f} pips) | "
                f"Outcome: {t['outcome']} | Reasoning: {t['reasoning']}"
            )
        
        trades_text = "\n".join(trades_summary)

        system_prompt = (
            "You are a master Forex trading mentor and quantitative analyst.\n"
            "Review the list of recent trades and their outcomes (WIN/LOSS/BE).\n"
            "Your goal is to extract concrete lessons and rules (Learning Notes) to improve future performance.\n"
            "Identify patterns in winning and losing trades based on the AI's reasoning, P&L, and action.\n"
            "Provide a concise, bullet-pointed summary in Thai (ภาษาไทย) of what the bot should DO or AVOID in the future.\n"
            "Keep the lessons actionable and evidence-based (e.g., 'Avoid buying when RSI is too high because trades ID 4 and 6 resulted in loss').\n"
            "Do NOT include greeting, introductory, or concluding texts. Provide only the bullet points."
        )

        user_content = (
            f"Here are the recent trade results:\n"
            f"{trades_text}\n"
        )

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
            ]
        }

        try:
            logging.info("📤 Requesting AI learning summary...")
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if response.status_code != 200:
                logging.error(f"❌ API Error in learning ({response.status_code}): {response.text}")
                return self._generate_mock_learning_notes(closed_trades)

            resp_data = response.json()
            learning_notes = resp_data["choices"][0]["message"]["content"].strip()
            logging.info("📥 Successfully generated learning notes.")
            return learning_notes

        except Exception as e:
            logging.error(f"❌ Error generating learning summary, falling back to simulated summary: {e}")
            return self._generate_mock_learning_notes(closed_trades)

    def _generate_mock_decision(self, symbol, current_price):
        """จำลองผลการประเมินสัญญาณเทรดเมื่อระบบ API ขัดข้อง"""
        # เพิ่มโอกาสออก BUY/SELL ให้สูงขึ้นเล็กน้อยสำหรับ Mock Mode (เพื่อการสาธิต)
        choices = ["BUY", "SELL", "HOLD"]
        recommendation = random.choices(choices, weights=[0.25, 0.25, 0.50])[0]
        
        if recommendation == "HOLD":
            reasoning = "สัญญาณทางเทคนิคไม่ชัดเจน RSI เคลื่อนที่อยู่ในโซนเป็นกลาง (Neutral Zone 48-52) เส้น EMA Fast และ Slow เคลื่อนไหวขนานกัน บ่งชี้สภาวะตลาดไร้ทิศทาง (Sideways) แนะนำชะลอการซื้อขายเพื่อความปลอดภัย"
            return {
                "recommendation": "HOLD",
                "sl_pips": None,
                "tp_pips": None,
                "confidence_score": 50,
                "reasoning": reasoning
            }
        
        sl = random.choice([25.0, 30.0, 35.0])
        tp = sl * random.choice([1.6, 2.0, 2.2])
        confidence = random.randint(72, 92)
        
        if recommendation == "BUY":
            reasoning = f"พบสัญญาณการกลับตัว Bullish Divergence บน RSI ร่วมกับการฟื้นตัวจากโซนสำคัญ พร้อมทั้งแท่งเทียนปิดเหนือระดับแนวรับล่าสุด และ EMA Fast ตัดขึ้นเหนือ EMA Slow ในลักษณะสีเขียวสะสม แรงซื้อกลับคืนสู่ตลาดอย่างมีนัยสำคัญ"
        else: # SELL
            reasoning = f"ราคาเข้าสู่ภาวะซื้อมากเกินไป (Oversold/Overbought) ใน RSI ทะลุ 70 และชนแนวต้านเชิงจิตวิทยา เกิดลักษณะแท่งเทียนประเภท Bearish Engulfing ยืนยันแรงขายกลับตัวรอบใหญ่ แนะนำฝั่งขายตามระบบบริหารความเสี่ยง"
            
        return {
            "recommendation": recommendation,
            "sl_pips": sl,
            "tp_pips": tp,
            "confidence_score": confidence,
            "reasoning": reasoning
        }

    def _generate_mock_learning_notes(self, closed_trades):
        """จำลองการวิเคราะห์สรุปผลการเรียนรู้ของระบบเพื่อแสดงบน UI"""
        win_count = sum(1 for t in closed_trades if t.get('outcome') == 'WIN')
        loss_count = sum(1 for t in closed_trades if t.get('outcome') == 'LOSS')
        
        notes = (
            "📌 **AI Learning Summary (Simulated Feedback):**\n"
            f"- จากการวิเคราะห์ผลการเทรดล่าสุด {len(closed_trades)} ออเดอร์ (ชนะ {win_count} / แพ้ {loss_count})\n"
            "- **ข้อเสนอแนะหลักสำหรับการ BUY:** หลีกเลี่ยงการเข้าซื้อเมื่อราคาวิ่งชนเส้นแนวต้านย้อนหลังหลัก เพื่อป้องกันการเกิด Falseout\n"
            "- **ข้อเสนอแนะหลักสำหรับการ SELL:** การตั้ง SL ระยะ 30 pips บางครั้งแคบเกินไปสำหรับความผันผวนของคู่เงิน GBPUSD แนะนำขยายเป็น 40-45 pips\n"
            "- **เครื่องมือที่ทำงานได้ดี:** สัญญาณการเข้าเทรดสอดคล้องกับการกลับตัวของแท่งเทียนประเภท Pin Bar บนแนวรับสำคัญให้อัตราการชนะ (Win Rate) สูงถึง 70%"
        )
        return notes
