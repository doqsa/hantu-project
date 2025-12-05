import asyncio
import pandas as pd
import pandas_ta as ta  # [추가] 정확한 지표 계산용
import aiohttp          # [추가] 과거 데이터 조회용
from collections import deque
from datetime import datetime

class StrategyManager:
    def __init__(self, strategy_queue, order_queue, token_manager):
        """
        :param token_manager: REST API로 과거 데이터를 긁어오기 위해 필요
        """
        self.strategy_queue = strategy_queue
        self.order_queue = order_queue
        self.token_manager = token_manager # 토큰 매니저 추가
        
        # 1분봉 데이터 저장소 (DataFrame으로 관리하는 게 지표 계산에 더 유리함)
        # 컬럼: [time, open, high, low, close]
        self.ohlc_data = pd.DataFrame(columns=['time', 'open', 'high', 'low', 'close'])
        
        self.current_minute_ticks = []
        self.last_minute = None
        
        # 상태 관리
        self.current_state = "EMPTY" 
        self.avg_price = 0
        
        # KODEX 200 종목코드 (필요시 변경 가능하게 설정)
        self.code = "069500"

    async def fetch_initial_data(self):
        """ [웜업] 장 시작 전, REST API로 과거 1분봉 100개를 가져와 채워넣음 """
        print("[Strategy] [데이터] 과거 데이터 요청 중... (Waiting 방지)")
        
        url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.token_manager.manage_token()}",
            "appkey": self.token_manager.app_key,
            "appsecret": self.token_manager.app_secret,
            "tr_id": "FHKST03010200"
        }
        
        # 현재 시간 기준 과거 조회
        now_time = datetime.now().strftime("%H%M%S")
        params = {
            "FID_ETC_CLS_CODE": "",
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": self.code,
            "FID_INPUT_HOUR_1": now_time,
            "FID_PW_DATA_INCU_YN": "Y"
        }

        try:
            print(f"[Strategy] API 요청 시작: {url}")
            async with aiohttp.ClientSession() as session:
                print("[Strategy] 세션 생성 완료")
                async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    print(f"[Strategy] 응답 상태: {response.status}")
                    data = await response.json()
                    print(f"[Strategy] 응답 데이터: {data.get('rt_cd')}, {data.get('msg1')}")
                    
                    if data.get('rt_cd') == '0':
                        items = data.get('output2', [])
                        print(f"[Strategy] 데이터 개수: {len(items)}")
                        
                        # 과거 -> 현재 순으로 정렬
                        temp_list = []
                        for item in reversed(items):
                            temp_list.append({
                                'time': item['stck_cntg_hour'], # 예: 090100
                                'open': float(item['stck_oprc']),
                                'high': float(item['stck_hgpr']),
                                'low': float(item['stck_lwpr']),
                                'close': float(item['stck_prpr'])
                            })
                        
                        # DataFrame 초기화
                        self.ohlc_data = pd.DataFrame(temp_list)
                        print(f"[Strategy] [OK] 과거 데이터 {len(self.ohlc_data)}개 로드 완료! 즉시 매매 가능.")
                    else:
                        print(f"[Strategy] [경고] 초기 데이터 로드 실패: {data.get('msg1')}")
                        # 실패해도 계속 진행
                        self.ohlc_data = pd.DataFrame()
        except asyncio.TimeoutError:
            print("[Strategy] [오류] API 요청 타임아웃 (10초)")
            self.ohlc_data = pd.DataFrame()
        except Exception as e:
            print(f"[Strategy] [오류] 웜업 중 에러: {type(e).__name__}: {e}")
            self.ohlc_data = pd.DataFrame()

    def calculate_indicators(self):
        """ pandas-ta를 이용한 정밀 계산 """
        if len(self.ohlc_data) < 20:
            return None, None, None

        # 1. 볼린저 밴드 (20, 2)
        # BBL: Lower, BBM: Mid, BBU: Upper
        bb = ta.bbands(self.ohlc_data['close'], length=20, std=2)
        if bb is None: return None, None, None # 데이터 부족시 None 반환될 수 있음

        # 2. RSI (14)
        rsi_series = ta.rsi(self.ohlc_data['close'], length=14)

        # 마지막(최신) 값 추출
        # iloc[-1]은 가장 최근 데이터
        current_close = self.ohlc_data['close'].iloc[-1]
        
        # pandas_ta 컬럼명이 버전마다 다를 수 있으므로 안전하게 추출
        # BBL_20_2.0 또는 BBL_20_2 등으로 나올 수 있음
        bbl_col = [col for col in bb.columns if col.startswith('BBL')][0]
        lower_band = bb[bbl_col].iloc[-1]
        current_rsi = rsi_series.iloc[-1]

        return lower_band, current_rsi, current_close

    async def run(self):
        # [중요] 시작하자마자 데이터 채우기 (5분 대기 삭제)
        await self.fetch_initial_data()
        
        print("[Strategy] [시작] 실시간 전략 감시 시작 (BB + RSI)")
        
        try:
            while True:
                data = await self.strategy_queue.get()
                
                # 데이터 파싱
                current_price = float(data['price'])
                current_time_str = data['timestamp'] # 예: "2025-12-05 09:30:01"
                
                # "분" 추출 (YYYY-MM-DD HH:MM)
                current_minute = current_time_str[:16]

                # --- [분봉 생성 로직] ---
                if self.last_minute is None:
                    self.last_minute = current_minute
                
                # 분이 바뀌면 이전 분봉 확정 및 DataFrame에 추가
                if current_minute != self.last_minute:
                    if self.current_minute_ticks:
                        # 1분봉 데이터 확정 (시가, 고가, 저가, 종가)
                        minute_open = self.current_minute_ticks[0]
                        minute_high = max(self.current_minute_ticks)
                        minute_low = min(self.current_minute_ticks)
                        minute_close = self.current_minute_ticks[-1]
                        
                        # DataFrame에 새 행 추가
                        new_row = {
                            'time': self.last_minute, # 이전 분 시간
                            'open': minute_open,
                            'high': minute_high,
                            'low': minute_low,
                            'close': minute_close
                        }
                        # concat 사용 (pandas 최신 권장)
                        self.ohlc_data = pd.concat([self.ohlc_data, pd.DataFrame([new_row])], ignore_index=True)
                        
                        # 메모리 관리: 100개 넘으면 앞부분 삭제
                        if len(self.ohlc_data) > 100:
                            self.ohlc_data = self.ohlc_data.iloc[-100:]

                        # === 지표 계산 및 신호 판단 (봉 마감 기준) ===
                        lower_band, rsi, last_close = self.calculate_indicators()
                        
                        if lower_band is not None:
                            print(f"[전략] {self.last_minute[-5:]} | 💰:{last_close} | 하단:{lower_band:.0f} | RSI:{rsi:.1f}")
                            
                            # [진입 로직] b1
                            if self.current_state == "EMPTY":
                                if last_close < lower_band and rsi < 30:
                                    print(f"[매수] 과매도 포착! (b1)")
                                    await self.order_queue.put({
                                        "type": "BUY", "stage": "b1", "price": last_close
                                    })
                                    self.current_state = "HOLDING"
                                    self.avg_price = last_close
                    
                    # 초기화
                    self.current_minute_ticks = []
                    self.last_minute = current_minute
                
                # 틱 데이터 수집
                self.current_minute_ticks.append(current_price)

                # --- [실시간 익절 감시] (틱 단위) ---
                if self.current_state == "HOLDING":
                    # 목표가: 평단 + 0.3%
                    target_price = self.avg_price * 1.003
                    
                    if current_price >= target_price:
                        print(f"💰 [익절] 목표 달성! (s1) 현재가:{current_price}")
                        await self.order_queue.put({
                            "type": "SELL", "stage": "s1", "price": current_price
                        })
                        self.current_state = "EMPTY"
                        self.avg_price = 0

        except asyncio.CancelledError:
            print("[Strategy] 종료")
        except Exception as e:
            print(f"[Strategy] 오류: {e}")