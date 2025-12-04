import asyncio
import aiomysql
import os
from dotenv import load_dotenv

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(BASE_DIR, '.env')
load_dotenv(ENV_FILE)

class DBHandler:
    def __init__(self, db_queue: asyncio.Queue):
        self.db_queue = db_queue
        self.pool = None
        self.is_running = False
        
        # .env에서 DB 정보 로드
        self.host = os.getenv("DB_HOST", "127.0.0.1")
        self.user = os.getenv("DB_USER")
        self.password = os.getenv("DB_PASSWORD")
        self.db_name = os.getenv("DB_NAME", "hantu_db")
        self.port = int(os.getenv("DB_PORT", 3306))

    async def _init_pool(self):
        """DB 연결 풀 생성 (비동기)"""
        try:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.db_name,
                autocommit=True, # 로그성 데이터는 자동 커밋이 성능상 유리
                charset='utf8mb4'
            )
            print(f"[DB] 연결 풀 생성 완료 ({self.host}:{self.port})")
        except Exception as e:
            print(f"[치명적 오류] DB 연결 실패: {e}")
            raise e

    async def _insert_trade(self, conn, data):
        """KODEX 200 체결 데이터 저장"""
        # 테이블이 없다면 생략되거나 에러가 날 수 있으므로 테이블 생성 확인 필요
        # (이 코드는 kodex200_trade 테이블이 있다고 가정)
        sql = """
            INSERT INTO kodex200_trade (
                bsop_date, cntg_time, current_price, 
                volume, accum_volume, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        timestamp = data.get('timestamp')
        now_date = timestamp[:10].replace('-', '')
        now_time = timestamp[11:19].replace(':', '')
        
        args = (
            now_date, now_time, 
            data.get('현재가'), 
            data.get('체결량'), 
            data.get('누적거래량'),
            timestamp
        )
        async with conn.cursor() as cur:
            await cur.execute(sql, args)

    async def _insert_hoga(self, conn, data):
        """KODEX 200 호가 및 분석 지표 저장"""
        sql = """
            INSERT INTO kodex200_hoga (
                bsop_date, hoga_time, 
                imbalance_ratio, wap_ask, wap_bid, resistance_wall, support_wall,
                ask_price_1, ask_vol_1, ask_price_2, ask_vol_2, ask_price_3, ask_vol_3, ask_price_4, ask_vol_4, ask_price_5, ask_vol_5,
                ask_price_6, ask_vol_6, ask_price_7, ask_vol_7, ask_price_8, ask_vol_8, ask_price_9, ask_vol_9, ask_price_10, ask_vol_10,
                bid_price_1, bid_vol_1, bid_price_2, bid_vol_2, bid_price_3, bid_vol_3, bid_price_4, bid_vol_4, bid_price_5, bid_vol_5,
                bid_price_6, bid_vol_6, bid_price_7, bid_vol_7, bid_price_8, bid_vol_8, bid_price_9, bid_vol_9, bid_price_10, bid_vol_10,
                total_ask_qty, total_bid_qty, created_at
            ) VALUES (
                %s, %s, 
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s
            )
        """
        timestamp = data.get('timestamp')
        now_date = timestamp[:10].replace('-', '')
        now_time = timestamp[11:19].replace(':', '')

        # 매개변수 리스트 구성 (상당히 길지만 순서대로 매핑)
        args = [
            now_date, now_time,
            data.get('imbalance_ratio'), data.get('wap_ask'), data.get('wap_bid'),
            data.get('resistance_wall'), data.get('support_wall')
        ]
        
        # 매도 1~10단계
        for i in range(1, 11):
            args.append(data.get(f'매도호가{i}', 0))
            args.append(data.get(f'매도호가잔량{i}', 0))
            
        # 매수 1~10단계
        for i in range(1, 11):
            args.append(data.get(f'매수호가{i}', 0))
            args.append(data.get(f'매수호가잔량{i}', 0))
            
        # 총잔량 및 타임스탬프
        args.append(data.get('총매도잔량', 0))
        args.append(data.get('총매수잔량', 0))
        args.append(timestamp)

        async with conn.cursor() as cur:
            await cur.execute(sql, tuple(args))

    async def _insert_futures(self, conn, data):
        """KOSPI 200 선물 데이터 저장"""
        sql = """
            INSERT INTO kospi200_futures (
                bsop_date, cntg_time, futures_code,
                current_price, open_interest, volume, accum_volume,
                theory_price, basis, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        timestamp = data.get('timestamp')
        now_date = timestamp[:10].replace('-', '')
        now_time = timestamp[11:19].replace(':', '')
        
        args = (
            now_date, now_time,
            data.get('code'),        # futures_data.py에서 code 필드 추가했음
            data.get('현재가'),
            data.get('미결제약정'),
            data.get('체결량'),
            data.get('누적거래량'),
            data.get('이론가', 0.0),
            data.get('괴리율', 0.0), # 임시로 괴리율을 basis 컬럼에 매핑 (필요시 수정)
            timestamp
        )
        async with conn.cursor() as cur:
            await cur.execute(sql, args)

    async def _insert_nav(self, conn, data):
        """iNAV 및 괴리율 데이터 저장 (사용자 요청 코드 반영)"""
        sql = """
            INSERT INTO kodex200_nav (
                bsop_date, check_time, current_price, nav, disparity, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        timestamp = data.get('timestamp')
        now_date = timestamp[:10].replace('-', '') 
        now_time = timestamp[11:19].replace(':', '') 
        
        args = (
            now_date, now_time,
            data.get('price'),      
            data.get('nav'),
            data.get('disparity'),
            timestamp
        )
        async with conn.cursor() as cur:
            await cur.execute(sql, args)

    async def run(self):
        """DB 저장 루프 시작"""
        await self._init_pool()
        self.is_running = True
        print("[DB] 비동기 저장 모듈 가동 시작...")

        try:
            while self.is_running:
                try:
                    # 큐에서 데이터 대기
                    data = await self.db_queue.get()
                    dtype = data.get('type')

                    # 연결 풀에서 커넥션 획득하여 쿼리 실행
                    async with self.pool.acquire() as conn:
                        if dtype == 'TRADE':
                            await self._insert_trade(conn, data)
                        elif dtype == 'ORDERBOOK':
                            await self._insert_hoga(conn, data)
                        elif dtype == 'FUTURES':
                            await self._insert_futures(conn, data)
                        elif dtype == 'NAV': 
                            await self._insert_nav(conn, data)
                        else:
                            pass # 알 수 없는 데이터 타입

                    self.db_queue.task_done()
                    
                except Exception as e:
                    print(f"[DB 에러] 저장 중 오류 발생: {e}")
                    # 연결이 끊겼을 경우 등을 대비해 잠시 대기
                    await asyncio.sleep(0.1)
        
        except asyncio.CancelledError:
            print("[DB] 정상 종료됨")
            raise
        except Exception as e:
            print(f"[DB] 심각한 오류: {e}")

    def close(self):
        """DB 연결 풀 종료"""
        self.is_running = False
        if self.pool is not None:
            self.pool.close()
            print("[DB] 연결 풀 종료 완료")
