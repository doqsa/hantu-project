import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

# =========================================================
# 1. KIS 선물 실시간 체결(H0FCCNT0) 필드 정의
# =========================================================
# 참고: KIS API 문서 기준 (실제 데이터 순서와 일치해야 함)
KIS_FUTURES_FIELDS = [
    "체결시간",         # 0
    "현재가",           # 1 (소수점 2자리)
    "전일대비부호",     # 2
    "전일대비",         # 3
    "등락률",           # 4
    "체결량",           # 5
    "누적거래량",       # 6
    "누적거래대금",     # 7
    "체결구분",         # 8
    "미결제약정",       # 9 (★중요: 시장의 지속성/강도 판단)
    "미결제약정전일대비", # 10
    "이론가",           # 11
    "이론가대비괴리율",   # 12
    "매도호가1",        # 13
    "매수호가1",        # 14
    "체결강도",         # 15
    "괴리율"            # 16
]

class FuturesDataProcessor:
    def __init__(self, raw_queue: asyncio.Queue, strategy_queue: asyncio.Queue, db_queue: asyncio.Queue = None):
        """
        :param raw_queue: WebSocket_Handler에서 원시 데이터가 들어오는 큐
        :param strategy_queue: 파싱된 데이터를 전략 모듈로 보낼 큐
        :param db_queue: 파싱된 데이터를 DB 모듈로 보낼 큐 (None일 수 있음)
        """
        self.raw_queue = raw_queue
        self.strategy_queue = strategy_queue
        self.db_queue = db_queue
        print("[FuturesData] 선물 데이터 프로세서 초기화 완료. (DB 연동 포함)")

    def _parse_data(self, raw_msg: str) -> Optional[Dict[str, Any]]:
        """
        선물 원시 데이터를 파싱하고 숫자로 변환합니다.
        """
        try:
            # 1. 데이터 분리: 암호화플래그 | TR_ID | TR_KEY | 데이터
            # 예: 0|H0FCCNT0|101V3000|120000^350.50^...
            parts = raw_msg.split('|')
            
            # 데이터 구조가 파이프 4개로 구성되므로 길이를 4로 체크해야 안전함
            if len(parts) < 4: 
                print(f"[FuturesData] ⚠️ 잘못된 데이터 구조 (구분자 개수 부족): {raw_msg[:50]}...")
                return None

            tr_id = parts[1]     # H0FCCNT0
            body_part = parts[3] # 실제 데이터 부분 (120000^350.50^...)
            
            # TR ID 확인 (H0FCCNT0: 선물 체결)
            if "H0FCCNT0" not in tr_id:
                print(f"[FuturesData] ⚠️ 선물 데이터 아님 (TR_ID: {tr_id})")
                return None
            
            # 2. 바디 분리
            # 마지막 데이터에 \r\n 등이 붙어있을 수 있으므로 strip() 처리 권장
            body_values = body_part.strip().split('^')
            
            print(f"[FuturesData] 📥 선물 데이터 수신: 필드 {len(body_values)}개, 코드={parts[2]}, 첫 데이터={body_values[0] if body_values else '없음'}")
            
            # 필드 매핑 (데이터 개수에 맞춰 자르기)
            limit = min(len(body_values), len(KIS_FUTURES_FIELDS))
            processed = dict(zip(KIS_FUTURES_FIELDS[:limit], body_values[:limit]))

            # 3. 데이터 형변환 (String -> Float/Int)
            # 선물 가격은 소수점(0.00)이 포함될 수 있으므로 float으로 변환
            if '현재가' in processed:
                try:
                    processed['현재가'] = float(processed['현재가'])
                except: processed['현재가'] = 0.0

            if '미결제약정' in processed:
                try:
                    processed['미결제약정'] = int(processed['미결제약정'])
                except: processed['미결제약정'] = 0

            if '체결량' in processed:
                try:
                    processed['체결량'] = int(processed['체결량'])
                except: processed['체결량'] = 0
                
            if '누적거래량' in processed:
                try:
                    processed['누적거래량'] = int(processed['누적거래량'])
                except: processed['누적거래량'] = 0

            # 4. 메타데이터 추가
            # 선물 코드는 raw_msg의 parts[2]에 들어있음 (예: 101V3000)
            processed['code'] = parts[2]
            processed['type'] = 'FUTURES'
            processed['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            
            print(f"[FuturesData] ✅ 파싱 완료: 가격={processed.get('현재가')}, 미결제={processed.get('미결제약정')}")
            return processed

        except Exception as e:
            print(f"[FuturesData] ❌ 파싱 중 오류: {e} / Data: {raw_msg[:30]}...")
            return None

    async def run(self):
        """
        프로세서 실행 루프: 원시 데이터를 가져와 파싱 후 배포
        
        [주석 처리] 선물 거래 교육 이수 및 권한 신청 후 활성화 필요
        """
        print("[FuturesData] [대기중] 선물 거래 권한 신청 후 활성화 예정...")
        try:
            # 권한 신청까지는 무한 대기
            await asyncio.sleep(float('inf'))
        except asyncio.CancelledError:
            print("[FuturesData] 정상 종료됨")
            raise

# =========================================================
# 테스트 코드 (이 파일만 실행 시 작동)
# =========================================================
if __name__ == "__main__":
    async def test_main():
        # 가상의 큐 생성
        raw_q = asyncio.Queue()
        strat_q = asyncio.Queue()
        db_q = asyncio.Queue()
        
        processor = FuturesDataProcessor(raw_q, strat_q, db_q)
        
        # 프로세서 백그라운드 실행
        asyncio.create_task(processor.run())

        print("--- 테스트 데이터 주입 ---")
        # 가상의 선물 데이터 (실제 KIS 형식: 0|ID|KEY|DATA)
        # [수정된 포맷] 파이프(|) 4개 구조 준수
        mock_body = "123456^345.50^5^0.50^0.15^10^5000^10000^1^250000^0^345.00^0.0^345.60^345.40^0^0"
        mock_msg = f"0|H0FCCNT0|101V3000|{mock_body}"
        
        await raw_q.put(mock_msg)
        await asyncio.sleep(1)
        
        # 결과 확인
        if not strat_q.empty():
            res = await strat_q.get()
            print(f"✅ 결과 확인 성공:")
            print(f" - 종목코드: {res.get('code')}")
            print(f" - 현재가: {res.get('현재가')} (Float 확인)")
            print(f" - 미결제약정: {res.get('미결제약정')}")
        else:
            print("❌ 결과 없음 (파싱 실패)")

    asyncio.run(test_main())