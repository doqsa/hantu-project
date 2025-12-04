import asyncio
import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from dotenv import load_dotenv

# =========================================================
# 1. 모듈 임포트
# =========================================================
try:
    from core.token_manage import TokenManager
    from core.websocket_handler import WebSocketHandler
    from core.db_handler import DBHandler
    from core.strategy_manager import StrategyManager
    from core.order_manager import OrderManager
except ImportError as e:
    print(f"[오류] core 모듈 임포트 실패: {e}")
    sys.exit(1)

try:
    from data.kodex200_data import Kodex200DataProcessor
    from data.futures_data import FuturesDataProcessor
except ImportError as e:
    print(f"[오류] data 모듈 임포트 실패: {e}")
    sys.exit(1)

try:
    from exchange_fetcher import ExchangeFetcher
    from global_market_fetcher import GlobalMarketFetcher
except ImportError as e:
    print(f"[오류] Fetcher 모듈 임포트 실패: {e}")
    sys.exit(1)

load_dotenv()

# =========================================================
# 2. 로깅 설정
# =========================================================
def setup_logging():
    if not os.path.exists('logs'):
        os.makedirs('logs')

    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    file_handler = TimedRotatingFileHandler(
        filename='logs/system.log', 
        when='midnight', 
        interval=1, 
        backupCount=30, 
        encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_formatter)
    logger.addHandler(stream_handler)
    
    return logger

# =========================================================
# 3. 메인 비동기 함수
# =========================================================
async def main():
    logger = setup_logging()
    logger.info("=== [시스템 트레이딩 엔진 시동 (가상 매매 모드)] ===")

    # (0) 환경변수 체크
    required_env_vars = ["APP_KEY", "APP_SECRET", "CANO"]
    if not all(os.getenv(key) for key in required_env_vars):
        logger.critical("[설정 오류] .env 파일에 필수 키가 누락되었습니다.")
        return

    # (1) 인증
    try:
        token_manager = TokenManager()
        if not token_manager.manage_token():
            logger.critical("[오류] 토큰 발급 실패.")
            return
        logger.info("[인증] Access Token 준비 완료.")
    except Exception as e:
        logger.error(f"[인증 예외] {e}")
        return

    # (2) 큐 생성 (메모리 보호를 위해 maxsize 설정 권장)
    raw_queue = asyncio.Queue(maxsize=1000)
    strategy_queue = asyncio.Queue(maxsize=1000)
    order_queue = asyncio.Queue(maxsize=1000)
    db_queue = asyncio.Queue(maxsize=2000)

    # (3) 인스턴스 생성
    ws_handler = WebSocketHandler(raw_queue)
    db_handler = DBHandler(db_queue)

    kodex_processor = Kodex200DataProcessor(raw_queue, strategy_queue, db_queue)
    futures_processor = FuturesDataProcessor(raw_queue, strategy_queue, db_queue)

    order_manager = OrderManager(order_queue, db_queue)
    strategy_manager = StrategyManager(strategy_queue, order_queue)

    exchange_fetcher = ExchangeFetcher(token_manager, db_queue)
    global_fetcher = GlobalMarketFetcher(db_queue)

    # (4) 태스크 가동
    tasks = [
        asyncio.create_task(ws_handler.start_listening()),
        asyncio.create_task(db_handler.run()),
        asyncio.create_task(kodex_processor.run()),
        asyncio.create_task(futures_processor.run()),
        asyncio.create_task(exchange_fetcher.run()),
        asyncio.create_task(global_fetcher.run()),
        asyncio.create_task(strategy_manager.run()),
        asyncio.create_task(order_manager.run())
    ]

    logger.info("=== [시스템 가동 중] 자본금 194만원 가상 매매 시작 ===")
    
    # (5) 대기 및 종료 처리
    try:
        await asyncio.gather(*tasks)

    except KeyboardInterrupt:
        logger.info("\n=== [시스템 종료 요청] 사용자 중단 ===")

    except Exception as e:
        logger.exception(f"[시스템 예외 발생] {e}")

    finally:
        logger.info("[종료] 실행 중인 모든 태스크 정리 시작...")
        
        # 1. 소켓 연결 해제 (더 이상 데이터 안 들어오게)
        ws_handler.stop_listening()
        
        # 2. DB 큐에 남은 데이터 처리를 위해 짧은 대기
        logger.info("[종료] DB 큐 최종 처리 중... (2초 대기)")
        try:
            await asyncio.wait_for(db_queue.join(), timeout=2.0)
            logger.info("[종료] DB 큐가 비워졌습니다.")
        except asyncio.TimeoutError:
            logger.warning(f"[경고] DB 큐에 {db_queue.qsize()}개 항목이 남아있습니다. 강제 종료합니다.")
        
        # 3. 모든 태스크 취소(Cancel) 요청
        logger.info("[종료] 실행 중인 태스크 취소 중...")
        for task in tasks:
            if not task.done():
                task.cancel()
        
        # 4. 취소된 태스크들이 정리될 때까지 대기 (timeout 설정)
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), 
                timeout=3.0
            )
            
            # 5. 종료 상태 로깅
            for i, result in enumerate(results):
                if isinstance(result, asyncio.CancelledError):
                    pass  # 정상 취소
                elif isinstance(result, Exception):
                    logger.warning(f"[태스크 {i+1}] 종료 중 예외: {result}")
                    
        except asyncio.TimeoutError:
            logger.critical("[치명적 오류] 태스크 종료 타임아웃! 강제 종료합니다.")
        
        # 6. [중요] 모든 태스크가 끝난 뒤에 DB 연결 종료
        db_handler.close()
        
        logger.info("=== [시스템 종료 완료] 안전하게 셧다운되었습니다. ===")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())