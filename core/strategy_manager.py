import asyncio
import pandas as pd
import numpy as np
from collections import deque

class StrategyManager:
    def __init__(self, strategy_queue, order_queue):
        """
        :param strategy_queue: 데이터 프로세서에서 넘어온 시세 데이터 (Input)
        :param order_queue: 주문 매니저로 보낼 주문 신호 (Output)
        """
        self.strategy_queue = strategy_queue
        self.order_queue = order_queue
        
        # --- 지표 계산을 위한 데이터 버퍼 ---
        # 1분봉 생성을 위한 틱 데이터 임시 저장소
        self.current_minute_ticks = []
        self.last_minute = None
        
        # 지표 계산용 과거 종가 리스트 (최대 100개 유지)
        self.close_history = deque(maxlen=100)
        
        # 상태 관리 (EMPTY, HOLDING)
        self.current_state = "EMPTY" 
        self.avg_price = 0  # 평단가 (보유중일 때)

    def calculate_indicators(self):
        """ 볼린저 밴드(20,2)와 RSI(14) 계산 """
        if len(self.close_history) < 20:
            return None, None, None # 데이터 부족

        series = pd.Series(self.close_history)
        
        # 1. 볼린저 밴드 (20일 이동평균, 승수 2)
        ma20 = series.rolling(window=20).mean().iloc[-1]
        std = series.rolling(window=20).std().iloc[-1]
        upper = ma20 + (std * 2)
        lower = ma20 - (std * 2)
        
        # 2. RSI (14일)
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        return lower, rsi, series.iloc[-1] # 하단밴드, RSI, 현재가

    async def run(self):
        print("[Strategy] 전략 감시 시작 (BB + RSI 마틴게일)")
        
        try:
            while True:
                # 1. 실시간 데이터 수신
                data = await self.strategy_queue.get()
                
                # 틱 데이터에서 시간과 가격 추출
                # data format: {'code':..., 'price':..., 'timestamp':...}
                current_price = data['price']
                # 타임스탬프가 문자열이라면 변환 필요할 수 있음. 여기선 시:분만 추출한다고 가정
                # data['timestamp'] 예: "2025-12-05 09:30:01"
                current_time_str = data['timestamp'] # 초 단위까지 있다고 가정
                current_minute = current_time_str[:16] # "YYYY-MM-DD HH:MM" 까지만 잘라서 분 구분
                
                # --- 1분봉 생성 로직 ---
                if self.last_minute is None:
                    self.last_minute = current_minute
                
                if current_minute != self.last_minute:
                    # 분이 바뀌었음 -> 직전 분봉 확정 및 지표 계산
                    if self.current_minute_ticks:
                        close_p = self.current_minute_ticks[-1]
                        self.close_history.append(close_p)
                        
                        # 지표 계산
                        lower_band, rsi, last_close = self.calculate_indicators()
                        
                        if lower_band is not None:
                            # === [전략 판단 로직] ===
                            print(f"[전략] {self.last_minute[-5:]} | 가격:{last_close} | 하단:{lower_band:.0f} | RSI:{rsi:.1f}")
                            
                            # 1. 진입 (b1): 무포지션 AND 밴드하단 돌파 AND RSI<30
                            if self.current_state == "EMPTY":
                                if last_close < lower_band and rsi < 30:
                                    print(f"🚀 [매수 신호] 과매도 구간 포착! (b1 진입)")
                                    await self.order_queue.put({
                                        "type": "BUY", "stage": "b1", "price": last_close
                                    })
                                    self.current_state = "HOLDING"
                                    self.avg_price = last_close # (단순화: 체결 가정)

                            # 2. 청산 (s1) 또는 추가매수 (b2)는 실시간 가격으로 판단
                            # (여기서는 분봉 종가 기준으로 단순화했지만, 실전엔 틱마다 체크 가능)
                    
                    # 초기화
                    self.current_minute_ticks = []
                    self.last_minute = current_minute
                
                # 틱 데이터 모으기
                self.current_minute_ticks.append(current_price)

                # === [보유 중 실시간 감시] ===
                if self.current_state == "HOLDING":
                    # 익절 조건: 평단가 대비 0.3% 수익 (수수료 커버 후 수익)
                    target_price = self.avg_price * 1.003
                    
                    if current_price >= target_price:
                        print(f"💰 [익절 신호] 목표 수익 달성! (s1 청산)")
                        await self.order_queue.put({
                            "type": "SELL", "stage": "s1", "price": current_price
                        })
                        self.current_state = "EMPTY"
                        self.avg_price = 0
                    
                    # 물타기 조건 (b2): 평단가 대비 -0.5% 하락 시 (추후 구현)
                    # if current_price <= self.avg_price * 0.995: ...
        
        except asyncio.CancelledError:
            print("[Strategy] 정상 종료됨")
            raise
        except Exception as e:
            print(f"[Strategy] 오류 발생: {e}")