import requests
import json
import os
import math
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# --- 설정값 ---
# 한국투자증권 API 엔드포인트
URL_REAL = "https://openapi.koreainvestment.com:9443"
URL_VIRTUAL = "https://openapivts.koreainvestment.com:29443"

# [사용자 설정] 계좌 정보 (기본값)
# .env 파일에 값이 없으면 아래 값을 사용합니다.
DEFAULT_CANO = "43407510"       # 계좌번호 앞 8자리
DEFAULT_ACNT_PRDT_CD = "01"     # 계좌상품코드 2자리

# 수수료율 (이벤트 적용: 약 0.00404% -> 0.0000404 가정, 안전하게 조금 넉넉히 잡음)
FEE_RATE = 0.0000404

class AccountManager:
    def __init__(self, access_token):
        """
        :param access_token: Token_manage.py에서 발급받은 유효한 토큰
        """
        self.access_token = access_token
        self.app_key = os.getenv("APP_KEY")
        self.app_secret = os.getenv("APP_SECRET")
        
        # 계좌번호 설정 (.env 우선, 없으면 위에서 설정한 기본값 사용)
        # .env에서는 'CANO' 또는 기존 'ACCOUNT_NO' 키를 모두 확인합니다.
        self.account_no = os.getenv("CANO", os.getenv("ACCOUNT_NO", DEFAULT_CANO))
        self.acnt_prdt_cd = os.getenv("ACNT_PRDT_CD", DEFAULT_ACNT_PRDT_CD)
        
        self.trading_mode = os.getenv("TRADING_MODE", "VIRTUAL") # 기본값은 모의투자

        # 필수 환경변수 체크
        if not self.app_key or not self.app_secret:
            raise ValueError("[오류] .env 파일에 APP_KEY 또는 APP_SECRET이 없습니다.")
        
        if not self.account_no or len(self.account_no) != 8:
            raise ValueError(f"[오류] 계좌번호(CANO)는 8자리여야 합니다. 현재 값: {self.account_no}")

        # 모드에 따른 URL 및 TR_ID 설정
        if self.trading_mode == 'REAL':
            print(f"!!! [주의] 실전 투자(REAL) 모드로 초기화됩니다. 계좌: {self.account_no}-{self.acnt_prdt_cd} !!!")
            self.base_url = URL_REAL
            self.tr_id_balance = "TTTC8434R" # 주식 잔고 조회 (실전)
        else:
            print(f"--- 모의 투자(VIRTUAL) 모드로 초기화됩니다. 계좌: {self.account_no}-{self.acnt_prdt_cd} ---")
            self.base_url = URL_VIRTUAL
            self.tr_id_balance = "VTTC8434R" # 주식 잔고 조회 (모의)

    def get_headers(self, tr_id):
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id
        }

    def get_balance_and_holdings(self, target_code="069500"):
        """
        계좌 잔고와 특정 종목(KODEX 200 등)의 보유 현황(h1, h2...)을 조회합니다.
        :param target_code: 조회할 종목 코드 (기본: 069500 KODEX 200)
        :return: dict or None
        """
        path = "/uapi/domestic-stock/v1/trading/inquire-balance"
        url = f"{self.base_url}{path}"
        
        # 계좌번호 사용 (인스턴스 변수 활용)
        acc_prefix = self.account_no
        acc_suffix = self.acnt_prdt_cd

        params = {
            "CANO": acc_prefix,             # 종합계좌번호(8자리)
            "ACNT_PRDT_CD": acc_suffix,     # 계좌상품코드(2자리)
            "AFHR_FLPR_YN": "N",            # 시간외단일가여부
            "OFL_YN": "",                   # 공란
            "INQR_DVSN": "02",              # 조회구분 (02: 종목별)
            "UNPR_DVSN": "01",              # 단가구분
            "FUND_STTL_ICLD_YN": "N",       # 펀드결제분포함여부
            "FNCG_AMT_AUTO_RDPT_YN": "N",   # 융자금액자동상환여부
            "PRCS_DVSN": "00",              # 처리구분
            "CTX_AREA_FK100": "",           # 연속조회검색조건
            "CTX_AREA_NK100": ""            # 연속조회키
        }

        try:
            res = requests.get(url, headers=self.get_headers(self.tr_id_balance), params=params)
            
            if res.status_code != 200:
                print(f"[계좌 오류] API 호출 실패: {res.status_code}, {res.text}")
                return None
            
            data = res.json()
            if data['rt_cd'] != '0':
                print(f"[계좌 오류] API 응답 코드 에러: {data['msg1']}")
                return None

            # --- 데이터 파싱 ---
            holdings_list = data.get('output1', [])
            summary = data.get('output2', [])[0]

            # 1. 예수금 (주문 가능 현금)
            # dnca_tot_amt: 예수금총액 / prvs_rcdl_excc_amt: 가수도제외예수금(실질주문가능액)
            # 안전하게 '가수도제외예수금'을 사용하는 경우가 많으나, 여기선 예수금총액 사용
            cash_balance = int(summary.get('dnca_tot_amt', 0))
            total_asset = int(summary.get('tot_evlu_amt', 0))
            
            # 2. 목표 종목(h1, h2...) 보유 현황 찾기
            target_qty = 0
            target_avg_price = 0.0
            target_profit_rate = 0.0

            for stock in holdings_list:
                if stock['pdno'] == target_code:
                    target_qty = int(stock['hldg_qty'])       # 보유 수량
                    target_avg_price = float(stock['pchs_avg_pric']) # 매입 평균가
                    target_profit_rate = float(stock['evlu_pfls_rt']) # 수익률(%)
                    break

            return {
                "cash_balance": cash_balance,          # 주문 가능 현금 (원)
                "total_asset": total_asset,            # 총 평가 자산 (주식+현금)
                "stock_code": target_code,
                "held_qty": target_qty,                # 현재 보유량 (h 상태 확인용)
                "avg_price": target_avg_price,         # 평단가
                "profit_rate": target_profit_rate      # 현재 수익률
            }

        except Exception as e:
            print(f"[계좌 에러] 조회 중 예외 발생: {e}")
            return None

    def calc_max_buyable_qty(self, current_price, allocate_ratio=0.06):
        """
        [마틴게일 전략 - b1 진입 수량 계산]
        현재가(p) 기준으로 총 자산의 6% 비중만큼 매수 가능한 수량을 계산합니다.
        
        :param current_price: 현재 주가 (p)
        :param allocate_ratio: 사용할 자금 비율 (기본 0.06 = 6%)
        :return: 매수 가능 수량 (int)
        """
        # 1. 전체 자산 조회
        status = self.get_balance_and_holdings()
        
        # 조회 실패시 0 리턴 (안전장치)
        if not status: 
            print("[계산 실패] 잔고 조회 실패로 수량 계산 불가")
            return 0

        # 2. 1차 진입(b1) 목표 금액 계산 = 총 자산 * 6%
        target_amount = status['total_asset'] * allocate_ratio
        
        # 3. 실제 가용 현금과 비교 (돈이 없으면 있는 만큼만)
        available_cash = min(target_amount, status['cash_balance'])

        if available_cash <= 0: return 0

        # 4. 수수료 포함 최대 수량 계산
        # 필요 금액 = 주가 * 수량 * (1 + 수수료율)
        # 수량 = 가용자금 / (주가 * (1 + 수수료율))
        # KODEX 200은 가격단위가 있어서 소수점 발생 안하지만 floor처리
        max_qty = math.floor(available_cash / (current_price * (1 + FEE_RATE)))
        
        return int(max_qty)

# --- 테스트 코드 (AWS 서버 및 로컬 테스트용) ---
if __name__ == "__main__":
    # 토큰 파일이 있는지 확인
    token_file = 'access_token.json'
    if not os.path.exists(token_file):
        print(f"[오류] {token_file} 파일이 없습니다. Token_manage.py를 먼저 실행하세요.")
        exit()

    try:
        with open(token_file, 'r') as f:
            token_data = json.load(f)
            token = token_data.get('access_token')
            
        if not token:
            print("[오류] 토큰 파일 내용이 올바르지 않습니다.")
            exit()

        am = AccountManager(token)
        
        print(f">>> [{am.trading_mode}] 계좌 정보 조회 중...")
        info = am.get_balance_and_holdings("069500") # KODEX 200
        
        if info:
            print("-" * 40)
            print(f"💰 [자산] 총 평가 금액 : {info['total_asset']:,}원")
            print(f"💵 [현금] 주문 가능액 : {info['cash_balance']:,}원")
            print("-" * 40)
            print(f"📦 [보유] KODEX 200  : {info['held_qty']}주 (h{1 if info['held_qty']>0 else 0})")
            print(f"📊 [평단] 매입 평균가 : {info['avg_price']:,.0f}원")
            print(f"📈 [수익] 현재 수익률 : {info['profit_rate']}%")
            print("-" * 40)
            
            # 테스트 시뮬레이션
            mock_price = 30000 # p (현재가 가정)
            buy_qty = am.calc_max_buyable_qty(mock_price, 0.06) # 6% 비중
            
            required_money = buy_qty * mock_price
            print(f"🛒 [b1 시뮬레이션] 현재가 {mock_price:,}원 기준")
            print(f"   - 총 자산의 6% 할당")
            print(f"   - 계산된 주문 수량 : {buy_qty}주")
            print(f"   - 예상 소요 금액   : {required_money:,}원")
            print("-" * 40)

    except Exception as e:
        print(f"[테스트 실패] {e}")
        print("access_token.json 파일 확인 및 .env 설정을 확인하세요.")