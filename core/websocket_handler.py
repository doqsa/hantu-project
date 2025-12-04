import asyncio
import websockets
import json
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

# --- 경로 설정 (중요) ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(BASE_DIR, '.env')

# .env 파일 로드
load_dotenv(ENV_FILE)

# --- 설정값 ---
KODEX_200_CODE = "069500"  # KODEX 200

class WebSocketHandler:
    def __init__(self, queue: asyncio.Queue):
        # 1. 설정값 로드
        self.app_key = os.getenv("APP_KEY")
        self.app_secret = os.getenv("APP_SECRET")
        self.trading_mode = os.getenv("TRADING_MODE", "VIRTUAL")
        self.futures_code = os.getenv("FUTURES_CODE") 
        
        if not self.app_key or not self.app_secret:
            raise ValueError("[오류] .env 파일에 APP_KEY 또는 APP_SECRET이 없습니다.")
        
        self.queue = queue
        self.is_running = False
        
        # 2. 웹소켓 접속 URL 설정
        if self.trading_mode == 'REAL':
            self.BASE_URL = "https://openapi.koreainvestment.com:9443"
            self.WS_URL = "ws://ops.koreainvestment.com:21000"
        else:
            self.BASE_URL = "https://openapivts.koreainvestment.com:29443"
            self.WS_URL = "ws://ops.koreainvestment.com:21000" # 모의투자도 주소는 동일(포트 주의)

        # 3. 웹소켓 접속키(Approval Key) 발급 (동기 방식)
        self.approval_key = self._get_approval_key()

    def _get_approval_key(self):
        """웹소켓 연결을 위한 승인 키(Approval Key) 발급"""
        url = f"{self.BASE_URL}/oauth2/Approval"
        headers = {"content-type": "application/json; utf-8"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "secretkey": self.app_secret
        }
        
        try:
            print("[WS] 웹소켓 접속키 발급을 요청합니다...")
            res = requests.post(url, headers=headers, data=json.dumps(body))
            res.raise_for_status()
            key = res.json().get("approval_key")
            print(f"[WS] 접속키 발급 성공: {key[:10]}...")
            return key
        except Exception as e:
            raise RuntimeError(f"[치명적 오류] 웹소켓 접속키 발급 실패: {e}")

    def _create_subscription_payload(self, tr_id: str, item_code: str):
        """구독 요청 JSON 생성 (Approval Key 사용)"""
        # tr_type -> 1: 등록(구독), 2: 해제
        # custtype -> B: 법인, P: 개인 (API 문서는 보통 P 사용 권장이나 B도 됨, 여기선 P)
        payload = {
            "header": {
                "approval_key": self.approval_key,  # 여기가 핵심 변경 사항
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": tr_id,
                    "tr_key": item_code
                }
            }
        }
        return json.dumps(payload)

    async def _listener(self, websocket):
        """데이터 수신 및 큐 저장"""
        try:
            async for message in websocket:
                # 데이터 전처리 없이 날것 그대로 큐에 넘김 (분석은 다른 모듈에서)
                # print(f"[Debug] Raw WS Data: {message[:50]}...") # 디버깅용
                await self.queue.put(message)
                
        except websockets.ConnectionClosed:
            print("[WS] 서버와의 연결이 끊어졌습니다.")
        except Exception as e:
            print(f"[WS] 데이터 수신 중 오류: {e}")

    async def start_listening(self):
        """웹소켓 연결 및 구독 시작"""
        self.is_running = True
        print(f"\n--- [WS] 웹소켓 시스템 가동 ---")
        print(f"대상: KODEX 200({KODEX_200_CODE}), 선물({self.futures_code})")

        while self.is_running:
            try:
                # ping_interval=None: KIS는 자체 PING 퐁 방식이 다를 수 있어 자동 핑 끄거나 넉넉하게
                async with websockets.connect(self.WS_URL, ping_interval=60) as websocket:
                    print("[WS] 서버 연결 성공! 구독 패킷 전송 중...")

                    # 1. KODEX 200 체결가 (H0STCNT0)
                    await websocket.send(self._create_subscription_payload("H0STCNT0", KODEX_200_CODE))
                    
                    # 2. KODEX 200 호가 (H0STNHG0)
                    await websocket.send(self._create_subscription_payload("H0STNHG0", KODEX_200_CODE))

                    # 3. 선물 체결가 (H0FCCNT0) - 코드가 있을 때만
                    if self.futures_code:
                        await websocket.send(self._create_subscription_payload("H0FCCNT0", self.futures_code))
                        print(f"[WS] 선물({self.futures_code}) 구독 요청 완료")
                    
                    print(">>> 실시간 데이터 수신 중... <<<")
                    await self._listener(websocket)

            except Exception as e:
                print(f"[WS 재접속] 오류 발생: {e}")
                await asyncio.sleep(5) # 5초 후 재접속

    def stop_listening(self):
        self.is_running = False
        print("[WS] 종료 요청됨.")

# --- 테스트 코드 ---
if __name__ == "__main__":
    async def test_main():
        q = asyncio.Queue()
        handler = WebSocketHandler(q)
        
        # 백그라운드에서 리스닝 시작
        task = asyncio.create_task(handler.start_listening())

        print("--- 30초간 데이터 모니터링 시작 ---")
        start_time = datetime.now()
        
        try:
            while (datetime.now() - start_time).seconds < 30:
                try:
                    # 큐에서 데이터 꺼내오기 (타임아웃 2초)
                    data = await asyncio.wait_for(q.get(), timeout=2.0)
                    
                    # 데이터 간단 확인 (첫 글자가 0이나 1이면 실시간 데이터)
                    # KIS 데이터 포맷: 0|H0STCNT0|001|...
                    if isinstance(data, str) and "|" in data:
                        parts = data.split("|")
                        tr_id = parts[1] if len(parts) > 1 else "?"
                        
                        if "H0STCNT0" in tr_id:
                            print(f"[체결] KODEX 200 데이터 수신")
                        elif "H0STNHG0" in tr_id:
                            print(f"[호가] KODEX 200 호가 수신")
                        elif "H0FCCNT0" in tr_id:
                            print(f"[선물] 선물 체결 데이터 수신")
                        else:
                            print(f"[기타] {data[:30]}...")
                            
                    q.task_done()
                except asyncio.TimeoutError:
                    print("... 데이터 대기 중 ...")
                    
        except KeyboardInterrupt:
            print("테스트 중단")
        finally:
            handler.stop_listening()
            task.cancel()
            print("테스트 종료")

    asyncio.run(test_main())