import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional

# =========================================================
# 1. KIS 웹소켓 데이터 필드 정의 (상수)
# =========================================================

# [체결 데이터] TR ID: H0STCNT0
KIS_CNT_FIELDS = [
    "체결시간", "현재가", "전일대비부호", "전일대비", "등락률", 
    "매도호가", "매수호가", "체결량", "체결구분", "누적거래량", 
    "누적거래대금", "매도잔량", "매수잔량"
]

# [호가 데이터] TR ID: H0STASP0 (10단계 호가 - Pipe 구분)
KIS_HOGA_FIELDS = [
    "호가시간", "체결구분코드",
    "매도호가10", "매도호가9", "매도호가8", "매도호가7", "매도호가6",
    "매도호가5", "매도호가4", "매도호가3", "매도호가2", "매도호가1",
    "매수호가1", "매수호가2", "매수호가3", "매수호가4", "매수호가5",
    "매수호가6", "매수호가7", "매수호가8", "매수호가9", "매수호가10",
    "매도호가잔량10", "매도호가잔량9", "매도호가잔량8", "매도호가잔량7", "매도호가잔량6",
    "매도호가잔량5", "매도호가잔량4", "매도호가잔량3", "매도호가잔량2", "매도호가잔량1",
    "매수호가잔량1", "매수호가잔량2", "매수호가잔량3", "매수호가잔량4", "매수호가잔량5",
    "매수호가잔량6", "매수호가잔량7", "매수호가잔량8", "매수호가잔량9", "매수호가잔량10",
    "총매도호가잔량", "총매수호가잔량", "시간외총매도호가잔량", "시간외총매수호가잔량",
    "예상체결가", "예상체결량", "예상거래량", "예상체결대비", "부호", "예상등락률",
    "누적거래량", "주식영업일자", "누적거래대금", "총매도호가건수", "총매수호가건수"
]

class Kodex200DataProcessor:
    def __init__(self, raw_queue: asyncio.Queue, strategy_queue: asyncio.Queue, db_queue: asyncio.Queue):
        """
        :param raw_queue: WebSocket_Handler에서 원시 데이터가 들어오는 큐
        :param strategy_queue: 파싱 및 분석된 데이터를 전략 모듈로 보낼 큐
        :param db_queue: 데이터를 DB 핸들러로 보낼 큐 [추가됨]
        """
        self.raw_queue = raw_queue
        self.strategy_queue = strategy_queue
        self.db_queue = db_queue # [추가] DB 큐 저장
        print("[Kodex200Data] 데이터 프로세서 초기화 완료. (체결 + 호가 분석 + DB 연결)")

    # ---------------------------------------------------------
    # 2. 고급 분석 로직 (전략 지표 계산) - 기존 로직 유지
    # ---------------------------------------------------------
    def _analyze_hoga_pressure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """ 호가 데이터를 분석하여 가중평균가, 불균형, 지지/저항 벽을 계산 """
        w_ask_sum = 0
        w_bid_sum = 0
        total_ask_vol_10 = 0
        total_bid_vol_10 = 0
        
        max_ask_vol = 0
        ask_wall_price = 0
        max_bid_vol = 0
        bid_wall_price = 0

        for i in range(1, 11):
            # 매도(Ask)
            ask_p = data.get(f'매도호가{i}', 0)
            ask_v = data.get(f'매도호가잔량{i}', 0)
            if ask_p > 0:
                w_ask_sum += ask_p * ask_v
                total_ask_vol_10 += ask_v
                if ask_v > max_ask_vol:
                    max_ask_vol = ask_v
                    ask_wall_price = ask_p

            # 매수(Bid)
            bid_p = data.get(f'매수호가{i}', 0)
            bid_v = data.get(f'매수호가잔량{i}', 0)
            if bid_p > 0:
                w_bid_sum += bid_p * bid_v
                total_bid_vol_10 += bid_v
                if bid_v > max_bid_vol:
                    max_bid_vol = bid_v
                    bid_wall_price = bid_p

        wap_ask = round(w_ask_sum / total_ask_vol_10) if total_ask_vol_10 > 0 else 0
        wap_bid = round(w_bid_sum / total_bid_vol_10) if total_bid_vol_10 > 0 else 0
        
        # 총잔량 계산 (10단계 호가잔량 합산)
        total_ask_all = sum(data.get(f'매도호가잔량{i}', 0) for i in range(1, 11))
        total_bid_all = sum(data.get(f'매수호가잔량{i}', 0) for i in range(1, 11))
        if total_ask_all == 0: total_ask_all = 1  # 0 나누기 방지
        imbalance_ratio = round(total_bid_all / total_ask_all, 2) if total_ask_all > 0 else 0

        return {
            "wap_ask": wap_ask,
            "wap_bid": wap_bid,
            "imbalance_ratio": imbalance_ratio,
            "total_ask_all": total_ask_all,
            "total_bid_all": total_bid_all,
            "resistance_wall": ask_wall_price,
            "support_wall": bid_wall_price,
            "max_bid_vol": max_bid_vol,
            "max_ask_vol": max_ask_vol
        }

    # ---------------------------------------------------------
    # 3. 데이터 파싱 및 정제 (Parsing)
    # ---------------------------------------------------------
    def _parse_data(self, raw_msg: str) -> Optional[Dict[str, Any]]:
        try:
            parts = raw_msg.split('|')
            if len(parts) < 4: return None

            header_part = parts[1]
            body_part = raw_msg.split('|')[-1]

            if "H0STCNT0" in raw_msg:
                tr_id = "H0STCNT0"
                body_values = body_part.split('^')
            elif "H0STASP0" in raw_msg:
                tr_id = "H0STASP0"
                body_values = body_part.split('^')
            else:
                return None

            processed = {}

            # --- [CASE 1] 실시간 체결 데이터 (H0STCNT0) ---
            if tr_id == "H0STCNT0":
                if len(body_values) < len(KIS_CNT_FIELDS): return None
                processed = dict(zip(KIS_CNT_FIELDS, body_values))
                
                for k, v in processed.items():
                    if k in ["현재가", "전일대비", "체결량", "누적거래량", "매도호가", "매수호가"]:
                        try: processed[k] = int(v.replace(',', ''))
                        except: pass
                
                processed['type'] = 'TRADE'

            # --- [CASE 2] 실시간 호가 데이터 (H0STASP0) ---
            elif tr_id == "H0STASP0":
                limit = min(len(body_values), len(KIS_HOGA_FIELDS))
                processed = dict(zip(KIS_HOGA_FIELDS[:limit], body_values[:limit]))

                for k, v in processed.items():
                    if ("호가" in k or "잔량" in k or "거래" in k or "체결" in k) and isinstance(v, str):
                        try: processed[k] = int(v.replace(',', ''))
                        except: processed[k] = 0

                # 고급 지표 분석
                analysis = self._analyze_hoga_pressure(processed)
                processed.update(analysis) 
                processed['type'] = 'ORDERBOOK'
            else:
                return None

            processed['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            return processed

        except Exception as e:
            # 파싱 실패는 조용히 넘김
            return None

    # ---------------------------------------------------------
    # 4. 실행 루프 (Async Run)
    # ---------------------------------------------------------
    async def run(self):
        print("[Kodex200Data] 데이터 처리 루프 시작...")
        try:
            while True:
                try:
                    raw_msg = await self.raw_queue.get()
                    data = self._parse_data(raw_msg)
                    
                    if data:
                        # 1. 전략 모듈로 전송 (체결 데이터만)
                        if data['type'] == 'TRADE':
                            if 'code' not in data: 
                                data['code'] = '069500' # KODEX 200 코드 강제 주입
                            data['price'] = data.get('현재가', 0)
                            await self.strategy_queue.put(data)
                        
                        # 2. DB 핸들러로 전송
                        table_name = ""
                        if data['type'] == 'TRADE':
                            table_name = "kodex200_trade"
                        elif data['type'] == 'ORDERBOOK':
                            table_name = "kodex200_hoga"
                        
                        if table_name:
                            db_packet = {
                                "table": table_name,
                                "data": data
                            }
                            await self.db_queue.put(db_packet)

                        # (로그 출력 - 너무 빠르면 주석 처리)
                        # if data['type'] == 'TRADE':
                        #     print(f"✅ [체결] {data['현재가']}원 | {data['체결량']}주")

                    self.raw_queue.task_done()
                    
                except Exception as e:
                    print(f"[Kodex200Data] 루프 에러: {e}")
                    # 에러 발생 시 잠시 대기
                    await asyncio.sleep(0.1)
        
        except asyncio.CancelledError:
            print("[Kodex200Data] 정상 종료됨")
            raise
        except Exception as e:
            print(f"[Kodex200Data] 심각한 오류: {e}")

# =========================================================
# 테스트 코드 (데이터 흐름 시뮬레이션)
# =========================================================
if __name__ == "__main__":
    import random

    async def test_main():
        raw_q = asyncio.Queue()
        strat_q = asyncio.Queue()
        db_q = asyncio.Queue() # 테스트용 DB 큐
        
        # 인자 3개 전달
        processor = Kodex200DataProcessor(raw_q, strat_q, db_q)

        asyncio.create_task(processor.run())

        print("--- 테스트 데이터 주입 ---")
        # 가짜 체결 데이터
        dummy_cnt_list = ["120001", "35000", "5", "100", "0.5", "35005", "35000", "10", "1", "1000", "35000000", "50", "60"]
        dummy_cnt_msg = "0|H0STCNT0|001|" + "^".join(dummy_cnt_list)
        await raw_q.put(dummy_cnt_msg)
        
        await asyncio.sleep(1)
        
        if not db_q.empty():
            res = await db_q.get()
            print(f"DB 큐 수신 확인: {res['table']}")
        
        print("--- 테스트 종료 ---")

    asyncio.run(test_main())