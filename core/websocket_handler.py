import asyncio
import os
import json
import websockets
from aiohttp import ClientSession, TCPConnector

class WebSocketHandler:
    """
    KIS 웹소켓 접속 및 실시간 데이터 처리 핸들러입니다.
    """
    def __init__(self, raw_queue: asyncio.Queue):
        self.raw_queue = raw_queue
        self.ws = None
        self.is_listening = False
        self.approval_key = None
        self.ws_session = None
        
        # .env에서 환경 변수 로드 (main.py에서 로드되었음을 가정)
        self.APP_KEY = os.getenv("APP_KEY")
        self.APP_SECRET = os.getenv("APP_SECRET")
        self.WS_URL = "ws://ops.koreainvestment.com:21000"  # TR_ID 제거
        
        # KODEX 200 종목 코드
        self.KODEX_CODE = "069500" 

    async def _get_websocket_key(self):
        """[복구 함수] HTTP API를 통해 웹소켓 접속키 (Approval Key)를 발급받습니다."""
        
        TR_ID = "FHKST01010000"
        APPROVAL_URL = "https://openapi.koreainvestment.com:9443/oauth2/Approval"
        
        headers = {
            "content-type": "application/json",
            "appkey": self.APP_KEY,
            "appsecret": self.APP_SECRET,
        }
        
        data = {
            "grant_type": "client_credentials",
            "appkey": self.APP_KEY,
            "secretkey": self.APP_SECRET
        }

        try:
            async with ClientSession(connector=TCPConnector(ssl=False)) as session:
                print("[WS] 웹소켓 접속키 발급을 요청합니다...")
                async with session.post(APPROVAL_URL, headers=headers, data=json.dumps(data)) as response:
                    if response.status != 200:
                        print(f"[WS 오류] 웹소켓 접속키 API 응답 실패: {response.status}")
                        return False
                    
                    response_data = await response.json()
                    
                    if 'approval_key' in response_data:
                        self.approval_key = response_data['approval_key']
                        print(f"[WS] 접속키 발급 성공: {self.approval_key[:8]}...")
                        return True
                    else:
                        print(f"[WS 오류] 응답 데이터에 approval_key 없음: {response_data.get('msg1')}")
                        return False

        except Exception as e:
            print(f"[WS 치명적 오류] 접속키 발급 중 예외 발생: {e}")
            return False
    
    def _create_subscription_payload(self, tr_id: str, tr_key: str):
        """구독 요청 JSON 생성"""
        payload = {
            "header": {
                "approval_key": self.approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": tr_id,
                    "tr_key": tr_key
                }
            }
        }
        return json.dumps(payload)

    async def start_listening(self):
        """웹소켓 연결을 시작하고 실시간 데이터를 수신합니다."""
        
        if not self.approval_key:
            print("[WS] 오류: 웹소켓 접속키가 없어 연결을 시작할 수 없습니다.")
            return

        self.is_listening = True
        
        try:
            async with websockets.connect(self.WS_URL) as websocket:
                self.ws = websocket
                print("[WS] 서버 연결 성공! 구독 패킷 전송 중...")
                
                # 1. KODEX 200 체결가 (H0STCNT0) 구독
                await websocket.send(self._create_subscription_payload("H0STCNT0", self.KODEX_CODE))
                print("[WS] [OK] H0STCNT0 체결가 구독")
                
                # 2. KODEX 200 호가 (H0STASP0) 구독
                await websocket.send(self._create_subscription_payload("H0STASP0", self.KODEX_CODE))
                print("[WS] [OK] H0STASP0 호가 구독")
                
                print(">>> 실시간 데이터 수신 중... <<<")
                
                while self.is_listening:
                    try:
                        message = await self.ws.recv()
                        await self.raw_queue.put(message)
                        
                    except websockets.exceptions.ConnectionClosedOK:
                        print("[WS] 연결 정상 종료.")
                        break
                    except Exception as e:
                        print(f"[WS] 데이터 수신 중 오류: {e}")
                        break

        except Exception as e:
            print(f"[WS] 웹소켓 연결 실패: {e}")

        finally:
            self.is_listening = False

    def stop_listening(self):
        """웹소켓 수신 루프를 안전하게 종료합니다."""
        self.is_listening = False

    async def send_packet(self, packet: str):
        """[복구 함수] 외부에서 받은 구독 패킷을 웹소켓으로 직접 전송합니다."""
        if self.ws and not self.ws.closed:
            await self.ws.send(packet)
        else:
            print("[WS 경고] 웹소켓 연결이 닫혔거나 초기화되지 않아 전송 실패.")