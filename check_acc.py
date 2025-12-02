import requests
import json
import time
import urllib.parse
import os
from datetime import datetime, timedelta, timezone
from token_manage import get_token_for_api
import key  # key.py 파일에서 설정 불러오기

# =========================================================
# --- 1. 설정 변수 (key.py에서 불러오기) ---
# =========================================================
APP_KEY = key.APP_KEY
APP_SECRET = key.APP_SECRET
URL_BASE = key.URL_BASE
TOKEN_FILE = key.TOKEN_FILE
SECURITY_MARGIN = 60 * 10  # 토큰 만료 10분 전이면 갱신 시도 (안전 여유 시간)

# 잔고 조회용 설정
CANO = "43407510"  # 고객님의 계좌번호 8자리
ACNT_PRDT_CD = "01" # 계좌 상품 코드 (일반적으로 '01' 사용)
# =========================================================


# =========================================================
# --- 2. 위탁계좌(일반 주식계좌) 잔고 조회 ---
# =========================================================

def get_deposit_balance(token, app_key, cano, acnt_prdt_cd):
    """
    위탁계좌(일반 주식계좌)의 예수금 잔고 조회
    """
    print("\n🔍 위탁계좌 예수금 잔고 조회를 시작합니다...")
    
    PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
    URL = URL_BASE + PATH
    
    HEADERS = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": APP_SECRET,
        "tr_id": "TTTC8434R"  # 주식잔고조회 TR_ID
    }
    
    # 위탁계좌 조회용 파라미터
    PARAMS = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "N",
        "INQR_DVSN": "00",  # 전체조회
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",  # 펀드결제분 제외 (위탁계좌는 주식 위주)
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": ""
    }

    try:
        res = requests.get(URL, headers=HEADERS, params=PARAMS, timeout=10)
        response_data = res.json()
        
        print(f"📡 응답 상태: {res.status_code}")
        
        if res.status_code == 200 and response_data.get('rt_cd') == '0':
            print("✅ [위탁계좌 잔고 조회 성공]")
            print("=" * 60)
            
            # output2 (예수금 정보) 분석
            if response_data.get('output2') and len(response_data['output2']) > 0:
                cash_info = response_data['output2'][0]
                print("💰 [위탁계좌 예수금 정보]")
                
                # 주요 필드 출력
                important_fields = {
                    'dnca_tot_amt': '예수금 총액',
                    'nxdy_excc_amt': '출금가능금액',
                    'prvs_rcdl_excc_amt': '예수금',
                    'tot_evlu_amt': '총평가금액'
                }
                
                for field, description in important_fields.items():
                    value = cash_info.get(field, '0')
                    if value and str(value) != '0':
                        print(f"   {description}: {int(value):>15,} 원")
                
                # 투자가능 금액 및 6% 계산``
                tot_evlu_amt = int(cash_info.get('tot_evlu_amt', '0'))  # 총평가금액 (투자가능금액)
                six_percent = int(tot_evlu_amt * 0.06)
                
                print(f"\n📊 [투자 가능 금액 분석]")
                print(f"   투자가능금액: {tot_evlu_amt:>15,} 원")
                print(f"   6% 투자금액: {six_percent:>15,} 원")
                print(f"   (1회 최대 투자 권장금액)")
            
            # output1 (주식 보유 내역) 분석
            if response_data.get('output1'):
                print(f"\n📈 [보유 주식] {len(response_data['output1'])}개 종목")
                total_stock_value = 0
                for i, stock in enumerate(response_data['output1'], 1):
                    stock_qty = int(stock.get('hldg_qty', 0))
                    stock_value = int(stock.get('evlu_amt', 0))
                    
                    if stock_qty > 0:
                        print(f"   {i:2d}. {stock.get('prdt_name', 'N/A')}")
                        print(f"       종목코드: {stock.get('pdno', 'N/A')}")
                        print(f"       보유수량: {stock_qty:>8} 주")
                        print(f"       평가금액: {stock_value:>8,} 원")
                        total_stock_value += stock_value
                
                if total_stock_value > 0:
                    print(f"\n   💰 주식 총 평가금액: {total_stock_value:>15,} 원")
            else:
                print("\n📊 보유 주식이 없습니다.")
            
            print("=" * 60)
            return response_data
        else:
            error_msg = response_data.get('msg1', 'API 오류')
            print(f"❌ [위탁계좌 조회 실패]: {error_msg}")
            return None

    except Exception as e:
        print(f"❌ [위탁계좌 조회 오류]: {e}")
        return None


# =========================================================
# --- 3. 메인 실행 블록 ---
# =========================================================

if __name__ == "__main__":
    print("🚀 한국투자증권 계좌 조회 프로그램")
    print(f"📁 토큰 파일: {TOKEN_FILE}")
    print(f"👤 계좌번호: {CANO}-{ACNT_PRDT_CD}")
    
    # 토큰 관리 시스템을 통해 유효한 토큰을 가져옵니다.
    final_token = get_token_for_api(APP_KEY, APP_SECRET, URL_BASE)
    
    if final_token:
        print(f"🔑 토큰 획득 성공: {final_token[:30]}...")
        
        # 위탁계좌 잔고 조회
        result = get_deposit_balance(final_token, APP_KEY, CANO, ACNT_PRDT_CD)
        
        if result:
            print("\n🎉 계좌 조회가 완료되었습니다.")
            print("✅ 프로그램이 정상적으로 작동하고 있습니다!")
        else:
            print("\n❌ 계좌 조회에 실패했습니다.")
    else:
        print("💥 프로그램을 종료합니다. 유효한 토큰을 확보하지 못했음. ")