import asyncio
import math
from datetime import datetime

class OrderManager:
    def __init__(self, order_queue, db_queue):
        self.order_queue = order_queue
        self.db_queue = db_queue
        
        # --- 가상 계좌 설정 ---
        self.initial_capital = 1940000  # 초기 자본금 194만원
        self.current_balance = 1940000  # 현재 예수금
        self.holdings_qty = 0           # 보유 수량
        self.avg_price = 0              # 평단가
        self.fee_rate = 0.0000404       # 수수료 (이벤트가)

    async def run(self):
        print(f"[Order] 가상 매매 시스템 가동 (자본금: {self.current_balance:,}원)")
        
        try:
            while True:
                # 전략에서 주문 신호 수신
                signal = await self.order_queue.get()
                # signal format: {"type": "BUY", "stage": "b1", "price": 57000}
                
                order_type = signal['type']
                stage = signal['stage']
                price = int(signal['price'])
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if order_type == "BUY":
                    await self.execute_buy(stage, price, timestamp)
                elif order_type == "SELL":
                    await self.execute_sell(stage, price, timestamp)
        
        except asyncio.CancelledError:
            print("[Order] 정상 종료됨")
            raise
        except Exception as e:
            print(f"[Order] 오류 발생: {e}")

    async def execute_buy(self, stage, price, timestamp):
        """ 가상 매수 체결 처리 """
        # 수량 계산 (b1은 총 자산의 6%)
        # 마틴게일 b2는 b1의 2배수 등 로직 추가 가능
        
        target_amt = 0
        if stage == "b1":
            target_amt = self.initial_capital * 0.06 # 6%
        elif stage == "b2":
            target_amt = self.initial_capital * 0.12 # 12%

        # 매수 가능 수량 계산
        qty = math.floor(target_amt / price)
        if qty == 0: qty = 1 # 최소 1주

        trade_amt = price * qty
        fee = trade_amt * self.fee_rate
        total_cost = trade_amt + fee

        if self.current_balance < total_cost:
            print("[Order] 잔액 부족으로 가상 매수 실패")
            return

        # 잔고 업데이트
        self.current_balance -= total_cost
        
        # 평단가 재계산 (이동평균)
        total_qty = self.holdings_qty + qty
        total_invest = (self.avg_price * self.holdings_qty) + trade_amt
        self.avg_price = total_invest / total_qty
        self.holdings_qty = total_qty

        print(f"✅ [체결-매수] {stage} | {price:,}원 | {qty}주 | 잔액:{int(self.current_balance):,}원")

        # DB 저장을 위한 패킷 생성
        log_data = {
            "table": "paper_trade_history",
            "data": {
                "timestamp": timestamp,
                "code": "069500",
                "type": "BUY",
                "stage": stage,
                "price": price,
                "qty": qty,
                "total_value": trade_amt,
                "fee": fee,
                "balance_after": self.current_balance,
                "profit": 0
            }
        }
        await self.db_queue.put(log_data)

    async def execute_sell(self, stage, price, timestamp):
        """ 가상 매도 체결 처리 """
        if self.holdings_qty == 0: return

        trade_amt = price * self.holdings_qty
        fee = trade_amt * self.fee_rate
        # ETF라 세금 0원 가정
        net_income = trade_amt - fee

        # 수익금 계산
        buy_cost = self.avg_price * self.holdings_qty
        profit = net_income - buy_cost

        # 잔고 업데이트
        self.current_balance += net_income
        
        print(f"✅ [체결-매도] {stage} | {price:,}원 | {self.holdings_qty}주 | 수익:{int(profit):,}원")

        # 초기화
        self.holdings_qty = 0
        self.avg_price = 0

        # DB 저장
        log_data = {
            "table": "paper_trade_history",
            "data": {
                "timestamp": timestamp,
                "code": "069500",
                "type": "SELL",
                "stage": stage,
                "price": price,
                "qty": 0, # 전량 매도라 표시는 0 또는 매도 수량 기재
                "total_value": trade_amt,
                "fee": fee,
                "balance_after": self.current_balance,
                "profit": profit
            }
        }
        await self.db_queue.put(log_data)