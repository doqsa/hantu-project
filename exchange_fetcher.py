import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
import yfinance as yf # pip install yfinance

# .env 파일 로드
load_dotenv()

class ExchangeFetcher:
    def __init__(self, token_manager, exchange_queue: asyncio.Queue):
        """
        :param token_manager: 토큰 관리자 (KIS API 사용 시 필요, 현재 yfinance 사용으로 미사용이나 확장성 위해 유지)
        :param exchange_queue: 수집된 환율 데이터를 보낼 비동기 큐
        """
        self.token_manager = token_manager
        self.exchange_queue = exchange_queue
        self.trading_mode = os.getenv("TRADING_MODE", "VIRTUAL")
        
        # 추후 KIS API 사용을 위한 URL 설정 (현재 yfinance 로직엔 영향 없음)
        if self.trading_mode == 'REAL':
            self.base_url = "https://openapi.koreainvestment.com:9443"
        else:
            self.base_url = "https://openapivts.koreainvestment.com:29443"

    def _fetch_yfinance_sync(self):
        """
        [동기 함수] yfinance를 이용해 환율 데이터를 가져옵니다.
        이 함수는 별도 스레드에서 실행되어야 메인 루프를 막지 않습니다.
        """
        try:
            # USD/KRW 티커 (환율)
            ticker = yf.Ticker("KRW=X")
            
            # 당일 데이터 조회 (가장 최근 데이터)
            data = ticker.history(period="1d")
            
            if not data.empty:
                # 가장 최근 종가(Close) 사용
                current_rate = data['Close'].iloc[-1]
                
                return {
                    "type": "EXCHANGE",
                    "currency": "USD",
                    "rate": round(float(current_rate), 2),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                }
            return None
        except Exception as e:
            print(f"[환율 에러] yfinance 조회 실패: {e}")
            return None

    async def fetch_exchange_rate(self):
        """
        [비동기 래퍼] 동기 함수인 _fetch_yfinance_sync를
        스레드 풀(Executor)에서 실행하여 논블로킹으로 만듭니다.
        """
        loop = asyncio.get_running_loop()
        # run_in_executor(None, ...) -> 기본 스레드 풀 사용
        result = await loop.run_in_executor(None, self._fetch_yfinance_sync)
        return result

    async def run(self):
        print(f"[Exchange Fetcher] 환율 정보 감시 시작 ({self.trading_mode} 모드, 60초 간격)...")
        
        while True:
            try:
                # 비동기로 환율 가져오기
                data = await self.fetch_exchange_rate()
                
                if data:
                    # 큐에 데이터 넣기 (메인 로직에서 꺼내감)
                    await self.exchange_queue.put(data)
                    # 로그가 너무 많으면 주석 처리
                    # print(f"💵 [환율] USD/KRW: {data['rate']}원 ({data['timestamp']})")
                
                # 60초 대기
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                print("[Exchange Fetcher] 작업 취소됨")
                break
            except Exception as e:
                print(f"[Exchange Fetcher] 루프 에러: {e}")
                await asyncio.sleep(10) # 에러 발생 시 잠시 대기 후 재시도

# --- 테스트 코드 (이 파일만 단독 실행 시 작동) ---
if __name__ == "__main__":
    async def main():
        # 가짜 큐 생성
        q = asyncio.Queue()
        # 토큰 매니저는 None으로 넣어 테스트
        fetcher = ExchangeFetcher(token_manager=None, exchange_queue=q)
        
        # 1. 1회 조회 테스트
        print(">>> 1회 조회 테스트 중...")
        data = await fetcher.fetch_exchange_rate()
        print(f"결과: {data}")
        
        # 2. 루프 테스트 (3초만 돌고 종료)
        print(">>> 루프 실행 테스트 (Ctrl+C로 종료 가능)")
        task = asyncio.create_task(fetcher.run())
        
        try:
            # 큐에서 데이터 꺼내보기 모니터링
            while True:
                item = await q.get()
                print(f">>> [Main Queue] 수신 확인: {item}")
                q.task_done()
        except KeyboardInterrupt:
            task.cancel()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("테스트 종료")