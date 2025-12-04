import asyncio
import yfinance as yf
import pandas as pd
from datetime import datetime

class GlobalMarketFetcher:
    def __init__(self, global_queue: asyncio.Queue):
        """
        :param global_queue: 수집된 글로벌 지수 데이터를 보낼 비동기 큐
        """
        self.global_queue = global_queue
        # 수집할 대상 정의 (티커명)
        self.targets = {
            "USD_KRW": "KRW=X",   # 달러/원 환율
            "S&P500_F": "ES=F",   # S&P 500 선물 (실시간)
            "NASDAQ_F": "NQ=F"    # 나스닥 100 선물 (실시간)
        }

    def _fetch_sync(self):
        """
        [동기 함수] yfinance를 이용해 글로벌 지수를 한방에 조회
        별도 스레드에서 실행됨
        """
        try:
            # 딕셔너리의 값(티커들)만 공백으로 연결 ("KRW=X ES=F NQ=F")
            tickers = " ".join(self.targets.values())
            
            # 멀티 스레딩 다운로드, 진행바 숨김, auto_adjust=True로 경고 제거
            data = yf.download(tickers, period="1d", interval="1m", progress=False, auto_adjust=True)
            
            if data.empty:
                return []

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            result_pack = []

            # yfinance 최신 버전에 따른 데이터 접근 처리
            # 보통 data['Close']가 멀티인덱스이거나 단일 컬럼일 수 있음
            try:
                closes = data['Close']
            except KeyError:
                # 데이터 구조가 예상과 다를 경우 (다운로드 실패 등)
                return []

            # 마지막 행(최신 데이터) 추출
            latest = closes.iloc[-1]

            # 1. 환율 (USD_KRW)
            if 'KRW=X' in latest.index:
                val = latest['KRW=X']
                if pd.notna(val): # NaN이 아닌 경우만
                    result_pack.append({
                        "type": "GLOBAL",
                        "code": "USD_KRW",
                        "value": round(float(val), 2),
                        "timestamp": timestamp
                    })

            # 2. 나스닥 선물 (NASDAQ_F)
            if 'NQ=F' in latest.index:
                val = latest['NQ=F']
                if pd.notna(val):
                    result_pack.append({
                        "type": "GLOBAL",
                        "code": "NASDAQ_F",
                        "value": round(float(val), 2),
                        "timestamp": timestamp
                    })

            # 3. S&P 선물 (S&P500_F)
            if 'ES=F' in latest.index:
                val = latest['ES=F']
                if pd.notna(val):
                    result_pack.append({
                        "type": "GLOBAL",
                        "code": "S&P500_F",
                        "value": round(float(val), 2),
                        "timestamp": timestamp
                    })

            return result_pack

        except Exception as e:
            print(f"[글로벌 지수 에러] 동기 조회 실패: {e}")
            return []

    async def fetch_data(self):
        """
        [비동기 래퍼] _fetch_sync를 스레드 풀에서 실행
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_sync)

    async def run(self):
        print("[Global Fetcher] 글로벌 거시 지표 감시 시작 (1분 간격)...")
        while True:
            try:
                results = await self.fetch_data()
                
                if results:
                    for item in results:
                        await self.global_queue.put(item)
                        # 로그 확인용 (너무 많으면 주석 처리)
                        # print(f"🌍 [{item['code']}] {item['value']}")
                
                # 1분 대기
                await asyncio.sleep(60)
            
            except asyncio.CancelledError:
                print("[Global Fetcher] 종료 요청 받음")
                break
            except Exception as e:
                print(f"[Global Fetcher] 루프 에러: {e}")
                await asyncio.sleep(10)

# --- 테스트 코드 ---
if __name__ == "__main__":
    async def main():
        q = asyncio.Queue()
        fetcher = GlobalMarketFetcher(q)
        
        print(">>> 1회 조회 테스트...")
        data = await fetcher.fetch_data()
        print(f"수신 데이터 개수: {len(data)}")
        for d in data:
            print(d)

    asyncio.run(main())