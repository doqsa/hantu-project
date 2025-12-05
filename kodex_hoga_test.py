import asyncio
import os
import sys
import json
import time 
from datetime import datetime
from dotenv import load_dotenv

# =========================================================
# 1. KIS 상수 정의
# =========================================================
KODEX_CODE = "069500"  # KODEX 200 ETF
HOGA_TR_ID = "H0STNHG0" # 주식 호가 데이터 TR ID (현물용)

# =========================================================
# 2. 모듈 임포트
# =========================================================
try:
    from core.token_manage import TokenManager
    from core.websocket_handler import WebSocketHandler
except ImportError as e:
    print(f"[오류] core 모듈 임포트 실패. 경로를 확인하세요: {e}")
    sys.exit(1)

# .env 파일 로드
load_dotenv()

# =========================================================
# 3. 웹소켓 구독 패킷 생성 함수
# =========================================================
def create_hoga_subscription_packet(approval_key: str) -> str:
    """KODEX 200 호가 데이터 구독 요청을 위한 KIS JSON 패킷을 생성합니다."""
    packet = {
        "header": {
            "approval_key": approval_key,
            "custtype": "P", 
            "tr_type": "1",  # 1: 등록 (구독)
            "tr_id": HOGA_TR_ID
        },
        "body": {
            "input": {
                "item_cd": KODEX_CODE
            }
        }
    }
    return json.dumps(packet)

# =========================================================
# 4. 메인 비동기 실행 함수
# =========================================================
async def main():
    print(f"=== [KODEX 200 호가 구독 테스트 시작: {HOGA_TR_ID}] ===")

    # (1) 인증 및 토큰 관리
    token_manager = TokenManager()
    if not token_manager.manage_token():
        print("[인증 오류] Access Token 발급 실패.")
        return
    
    # (2) 웹소켓 핸들러 초기화
    raw_queue = asyncio.Queue()
    ws_handler = WebSocketHandler(raw_queue)
    
    # 🚨 [AttributeError 방지] _get_websocket_key를 명시적으로 호출
    if not await ws_handler._get_websocket_key():
        print("[WS 오류] 웹소켓 접속키(Approval Key) 발급 실패.")
        return
        
    approval_key = ws_handler.approval_key
    print(f"--- [DEBUG 7] WebSocket Key Success: {approval_key[:8]}... ---")
    
    # (3) 웹소켓 연결 시작 및 구독 요청
    subscription_packet = create_hoga_subscription_packet(approval_key)
    
    # 웹소켓 연결 및 리스닝 태스크 시작
    ws_task = asyncio.create_task(ws_handler.start_listening())
    
    # 연결 성공을 기다리기 위해 잠시 대기
    await asyncio.sleep(2) 
    
    # 구독 패킷 전송
    try:
        print(f"[WS] 호가 데이터 구독 요청 전송: {KODEX_CODE} ({HOGA_TR_ID})")
        # send_packet 함수 존재 가정
        await ws_handler.send_packet(subscription_packet) 
    except AttributeError as e:
        print(f"❌ [치명적 오류] 구독 패킷 전송 실패: {e}")
        print("💡 조치: core/websocket_handler.py 파일에 send_packet 함수를 추가했는지 확인하세요.")
        return
    except Exception as e:
        print(f"[WS 오류] 구독 패킷 전송 실패: {e}")
        return

    # (4) 실시간 데이터 수신 확인 루프
    print("\n>>> 실시간 호가 데이터 수신 대기 중... (10초 대기) <<<")
    start_time = datetime.now()
    
    try:
        while (datetime.now() - start_time).seconds < 10:
            if not raw_queue.empty():
                raw_msg = await raw_queue.get()
                
                # 오류 메시지 확인
                if "invalid tr_key" in raw_msg or "OPSP8993" in raw_msg:
                    print(f"❌ [심각 오류] 호가 구독 거부: {raw_msg}")
                    print("❌ 오류 원인: 웹소켓 접속키가 유효하지 않습니다.")
                    break
                
                # 호가 데이터 수신 확인 (H0STNHG0 메시지 확인)
                if HOGA_TR_ID in raw_msg:
                    print(f"✅ [SUCCESS] 호가 데이터 수신! (부분 출력): {raw_msg[:100]}...")
                    if raw_queue.qsize() > 10:
                        break
                
                raw_queue.task_done()
            await asyncio.sleep(0.1)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[테스트 예외] {e}")

    finally:
        print("\n=== [테스트 종료] 소켓 연결 정리 ===")
        ws_handler.stop_listening()
        ws_task.cancel()
        await asyncio.gather(ws_task, return_exceptions=True)


if __name__ == "__main__":
    print("--- [DEBUG 8] Starting Async Run ---")
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())