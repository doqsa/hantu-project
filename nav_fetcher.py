import asyncio
import aiohttp
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- 설정값 ---
# 시세 조회는 항상 실전 서버(Real)를 사용하는 것이 좋습니다. (모의투자는 NAV 데이터 누락 가능성 있음)
URL_REAL = "https://openapi.koreainvestment.com:9443"

class NAVFetcher:
    def __init__(self, token_manager, nav_queue: asyncio.Queue):
        """
        :param token_manager: Token_manage.py의 인스턴스
        :param nav_queue: 수집한 데이터를 보낼 비동기 큐
        """
        self.token_manager = token_manager
        self.nav_queue = nav_queue
        
        self.app_key = os.getenv("APP_KEY")
        self.app_secret = os.getenv("APP_SECRET")
        
        # [중요] 시세/NAV 데이터는 모의투자 모드여도 '실전 서버' URL을 사용합니다.
        self.base_url = URL_REAL
        
        # 현재 사용 중인 토큰 캐싱 (매번 파일 읽지 않도록)
        self.current_token = None

    def _is_market_open(self):
        """현재 시간이 장 운영 시간(09:00 ~ 15:45)인지 확인 (장마감 동시호가 포함 넉넉히)"""
        now = datetime.now()
        
        # 주말 체크 (0:월 ~ 6:일)
        if now.weekday() >= 5:
            return False
            
        start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=15, minute=45, second=0, microsecond=0)
        
        return start_time <= now <= end_time

    async def fetch_nav(self, item_code="069500"):
        """REST API로 KODEX 200의 iNAV 및 현재가를 조회합니다."""
        path = "/uapi/domestic-stock/v1/quotations/inquire-price"
        url = f"{self.base_url}{path}"
        
        # 토큰이 없으면 로드
        if not self.current_token:
            self.current_token = self.token_manager.manage_token()

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.current_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010100" # 주식/ETF 현재가 시세 TR ID (실전용)
        }
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J", # 주식, ETF 포함
            "FID_INPUT_ISCD": item_code    # 종목코드 (069500)
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
                    
                    # 토큰 만료 에러(E_ or 401 등) 발생 시 토큰 갱신 로직이 필요할 수 있음
                    # 여기서는 간단히 성공 여부만 체크
                    
                    if data.get('rt_cd') == '0':
                        output = data['output']
                        
                        # API 응답 필드 확인
                        nav_str = output.get('nav', '0.0')
                        price_str = output.get('stck_prpr', '0')
                        
                        # 가끔 NAV가 비어있는 경우 방어 코드
                        if not nav_str: nav_str = '0.0'
                        
                        nav_val = float(nav_str)
                        price_val = float(price_str)
                        
                        # NAV가 0이면 괴리율 계산 불가
                        if nav_val == 0:
                            return None

                        # 괴리율 계산: (현재가 - NAV) / NAV * 100
                        disparity = ((price_val - nav_val) / nav_val) * 100
                        
                        result = {
                            "type": "NAV",
                            "code": item_code,
                            "nav": nav_val,
                            "price": price_val,
                            "disparity": round(disparity, 4),
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        return result
                    else:
                        # 오류 메시지 출력 (토큰 만료일 수도 있음)
                        msg = data.get('msg1', 'Unknown Error')
                        print(f"[NAV API 오류] {msg}")
                        return None

        except Exception as e:
            print(f"[NAV Fetcher 예외] {e}")
            return None

    async def run(self):
        print("[NAV Fetcher] 모듈 시작됨...")
        
        while True:
            # 1. 장 운영 시간 체크
            if not self._is_market_open():
                print(f"[휴장] 장 운영 시간이 아닙니다. 대기 중... ({datetime.now().strftime('%H:%M:%S')})")
                await asyncio.sleep(60) # 1분 대기
                continue

            # 2. 데이터 조회
            nav_data = await self.fetch_nav("069500")
            
            if nav_data:
                # 3. 큐에 전송 (Strategy 등으로 전달)
                await self.nav_queue.put(nav_data)
                
                # 로그 (너무 자주 찍히면 주석 처리)
                # print(f"📡 [NAV] {nav_data['price']}원 (NAV: {nav_data['nav']} | 괴리: {nav_data['disparity']}%)")
            
            # 4. API 호출 제한 준수 (초당 1~2회 권장)
            await asyncio.sleep(0.5) 

# --- 테스트 코드 ---
if __name__ == "__main__":
    # 이 부분은 Token_manage.py가 같은 폴더에 있어야 실행 가능합니다.
    try:
        from Token_manage import TokenManager
        
        async def test():
            print(">>> NAV Fetcher 테스트 시작 (Ctrl+C로 종료)")
            q = asyncio.Queue()
            tm = TokenManager() # 토큰 매니저 인스턴스
            
            nf = NAVFetcher(tm, q)
            
            # 테스트를 위해 강제로 run 실행
            # 주의: 장 운영 시간이 아니면 "대기 중"만 출력될 수 있음
            # 강제로 한 번만 찍어보기:
            print(">>> 1회 강제 조회 시도...")
            data = await nf.fetch_nav("069500")
            print(f"결과: {data}")
            
            # 실제 루프 실행
            # await nf.run() 

        asyncio.run(test())
        
    except ImportError:
        print("[오류] Token_manage.py 파일이 필요합니다.")