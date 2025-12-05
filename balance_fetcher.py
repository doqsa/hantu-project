import asyncio
import aiohttp
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class BalanceFetcher:
    def __init__(self, token_manager, balance_queue: asyncio.Queue):
        """
        :param token_manager: Token_manage.py의 인스턴스
        :param balance_queue: 수집한 데이터를 보낼 비동기 큐
        """
        self.token_manager = token_manager
        self.balance_queue = balance_queue
        
        self.app_key = os.getenv("APP_KEY")
        self.app_secret = os.getenv("APP_SECRET")
        self.cano = os.getenv("CANO")  # 계좌 앞자리
        self.acnt_prdt_cd = os.getenv("ACNT_PRDT_CD")  # 계좌 뒷자리
        
        # 실전 서버 URL
        self.base_url = "https://openapi.koreainvestment.com:9443"
        
        self.current_token = None

    def _is_market_open(self):
        """현재 시간이 장 운영 시간(09:00 ~ 15:45)인지 확인"""
        now = datetime.now()
        
        # 주말 체크
        if now.weekday() >= 5:
            return False
            
        start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=15, minute=45, second=0, microsecond=0)
        
        return start_time <= now <= end_time

    async def fetch_balance(self):
        """REST API로 계좌 잔고를 조회합니다."""
        path = "/uapi/domestic-stock/v1/trading/inquire-balance"
        url = f"{self.base_url}{path}"
        
        # 토큰이 없으면 로드
        if not self.current_token:
            self.current_token = self.token_manager.manage_token()

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.current_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "TQSBI0305"  # 잔고 조회 TR ID
        }
        
        params = {
            "CANO": self.cano,
            "ACNT_PRDT_CD": self.acnt_prdt_cd,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",  # 02: 종목별 요청
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_TRNF_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK": "",
            "CTX_AREA_NK": ""
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
                    
                    if data.get('rt_cd') == '0':
                        # 정상 응답
                        output1 = data.get('output1', {})
                        output2 = data.get('output2', [])
                        
                        result = {
                            "type": "BALANCE",
                            "total_purchase_amount": int(output1.get('tot_purc_amt', 0)),  # 총 매입금액
                            "total_eval_amount": int(output1.get('tot_evlu_amt', 0)),      # 총 평가금액
                            "total_gain_loss": int(output1.get('tot_gain_loss_amt', 0)),   # 총 손익금액
                            "total_gain_loss_rate": float(output1.get('tot_gain_loss_rate', 0)),  # 총 손익율
                            "deposit": int(output1.get('dpst_amt', 0)),                    # 예수금
                            "buy_power": int(output1.get('nass_amt', 0)),                  # 순매수력
                            "holdings": output2,  # 보유 종목 리스트
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        return result
                    else:
                        msg = data.get('msg1', 'Unknown Error')
                        print(f"[잔고 API 오류] {msg}")
                        return None

        except Exception as e:
            print(f"[잔고 Fetcher 예외] {e}")
            return None

    async def run(self):
        print("[Balance Fetcher] 계좌 잔고 조회 모듈 시작됨...")
        
        while True:
            # 1. 장 운영 시간 체크
            if not self._is_market_open():
                print(f"[휴장] 장 운영 시간이 아닙니다. 대기 중... ({datetime.now().strftime('%H:%M:%S')})")
                await asyncio.sleep(60)
                continue

            # 2. 데이터 조회
            balance_data = await self.fetch_balance()
            
            if balance_data:
                # 3. 큐에 전송
                await self.balance_queue.put(balance_data)
                
                # 로그
                print(f"💰 [잔고] 예수금: {balance_data['deposit']:,}원 | 평가: {balance_data['total_eval_amount']:,}원 | 손익: {balance_data['total_gain_loss']:,}원 ({balance_data['total_gain_loss_rate']:+.2f}%)")
            
            # 4. 5분 대기 (실시간성 필요시 60초로 변경)
            await asyncio.sleep(300)
