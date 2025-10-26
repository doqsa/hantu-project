import requests
import json
import time
import os
from datetime import datetime, timedelta, timezone

# =========================================================
# --- 1. 설정 변수 (App Key/Secret은 보안에 유의하세요) ---
# =========================================================
APP_KEY = "PSlNipf3HHE97a1T7l03GXxaMiwCVTLNu625" 
APP_SECRET = "U0zG3Htk6UUWliQaBSMBSvya92PqMEIKPjdmFSbjTUPyb9SPhtfmNPmfSLBpEQF5kZsYhJV8Uox1As8ahYCfOf/Y9YxVD//6vpNro0cc4V5QtlxtvdjWEVAvFzRIAv2Jya70HQVxdQm1fGOYERmaewtmM6p6BlTWgrenUvFyc5gS5QBzwEg=" 
URL_BASE = "https://openapi.koreainvestment.com:9443"
TOKEN_FILE = 'token-expire.json'
SECURITY_MARGIN = 60 * 10  # 토큰 만료 10분 전이면 갱신 시도 (안전 여유 시간)

# 잔고 조회용 설정
CANO = "43407510"  # 고객님의 계좌번호 8자리
ACNT_PRDT_CD = "01" # 계좌 상품 코드 (일반적으로 '01' 사용)
# =========================================================


# =========================================================
# --- 2. 토큰 관리 시스템 함수 정의 ---
# =========================================================

def save_new_token(app_key, app_secret):
    """API에 토큰을 요청하고 성공 시 JSON 파일에 저장."""
    PATH = "/oauth2/tokenP" 
    URL = URL_BASE + PATH

    HEADERS = {
        "Content-Type": "application/json"
    }
    
    BODY = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret
    }
    
    print("🔄 새 접근 토큰 발급을 시도합니다...")
    
    try:
        res = requests.post(URL, headers=HEADERS, data=json.dumps(BODY))
        if res.status_code != 200:
            print(f"❌ [토큰 발급 실패] 코드: {res.status_code}, 메시지: {res.text}")
            return None

        response_data = res.json()
        ACCESS_TOKEN = response_data['access_token']
        EXPIRES_IN_SECONDS = response_data.get('expires_in', 86400)
        
        now_utc = datetime.now(timezone.utc)
        expiry_utc = now_utc + timedelta(seconds=EXPIRES_IN_SECONDS)
        KST = timezone(timedelta(hours=9))
        expiry_kst = expiry_utc.astimezone(KST)

        token_data = {
            "access_token": ACCESS_TOKEN,
            "expires_in": EXPIRES_IN_SECONDS,
            "expiry_timestamp_utc": expiry_utc.timestamp(),
            "expiry_datetime_kst": expiry_kst.strftime("%Y-%m-%d %H:%M:%S")
        }

        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(token_data, f, indent=4)
        
        print(f"✅ [토큰 갱신 성공] KST 만료 시각: {token_data['expiry_datetime_kst']}")
        return ACCESS_TOKEN

    except requests.exceptions.RequestException as e:
        print(f"❌ [API 통신 오류] 토큰 발급 실패: {e}")
        return None
    except Exception as e:
        print(f"❌ [처리 오류] 데이터 처리 중 오류 발생: {e}")
        return None


def get_token_from_file():
    """저장된 파일에서 토큰을 읽어 유효성을 검사합니다."""
    if not os.path.exists(TOKEN_FILE):
        print("📄 [토큰 파일 없음] 저장된 토큰 파일이 없습니다.")
        return None
    
    try:
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            token_data = json.load(f)
    except Exception as e:
        print(f"❌ [토큰 파일 읽기 오류] 파일을 읽는 중 오류 발생: {e}")
        return None

    access_token = token_data.get('access_token')
    expiry_timestamp = token_data.get('expiry_timestamp_utc', 0)
    expiry_kst = token_data.get('expiry_datetime_kst', '알 수 없음')
    
    if not access_token:
        print("❌ [토큰 없음] 저장된 토큰 파일에 access_token이 없습니다.")
        return None

    current_timestamp = time.time()
    
    if current_timestamp < expiry_timestamp - SECURITY_MARGIN:
        print(f"✅ [토큰 재사용] 저장된 토큰이 유효하여 재사용합니다. (만료: {expiry_kst})")
        return access_token
    else:
        print(f"⚠️ [토큰 만료 임박] 저장된 토큰이 만료되었거나 곧 만료됩니다. (만료: {expiry_kst})")
        return None


def get_token_for_api():
    """유효한 토큰을 반환합니다. 필요 시 자동으로 갱신합니다."""
    token = get_token_from_file()
    
    if token:
        return token
    else:
        print("🔄 토큰 갱신이 필요하여 새 토큰을 발급합니다...")
        return save_new_token(APP_KEY, APP_SECRET)


# =========================================================
# --- 3. 시장 상태 조회 함수 ---
# =========================================================

def get_previous_business_day():
    """최근 영업일 계산 (주말, 공휴일 제외)"""
    today = datetime.now()
    # 최대 10일 전까지 확인
    for i in range(1, 11):
        previous_day = today - timedelta(days=i)
        # 월요일(0)부터 금요일(4)까지만 영업일
        if previous_day.weekday() <= 4:
            return previous_day.strftime("%Y%m%d")
    return today.strftime("%Y%m%d")


def get_market_status(access_token, market_id="0"):
    """시장 전체의 거래량 및 상태 조회
    market_id: 
    - "0": 코스피
    - "1": 코스닥
    """
    PATH = "/uapi/domestic-stock/v1/quotations/inquire-index"
    URL = URL_BASE + PATH
    
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {access_token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKUP03500100"  # 업종 지수 조회 TR
    }
    
    # 최근 영업일로 조회
    business_date = get_previous_business_day()
    
    params = {
        "FID_COND_MRKT_DIV_CODE": market_id,  # 시장구분코드
        "FID_INPUT_ISCD": "0001" if market_id == "0" else "1001",  # 코스피: 0001, 코스닥: 1001
        "FID_INPUT_DATE_1": business_date,  # 최근 영업일 지정
        "FID_INPUT_DATE_2": business_date   # 최근 영업일 지정
    }
    
    try:
        response = requests.get(URL, headers=headers, params=params)
        print(f"📡 시장 상태 API 응답 코드: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('rt_cd') == '0' and 'output' in data:
                market_data = data['output']
                return {
                    'index_name': market_data.get('hts_kor_isnm', ''),
                    'current_index': float(market_data.get('stck_prpr', '0')),
                    'volume': int(market_data.get('acml_vol', '0')),
                    'value': float(market_data.get('acml_tr_pbmn', '0')),
                    'change_rate': float(market_data.get('prdy_ctrt', '0')),
                    'trade_date': market_data.get('stck_bsop_date', ''),
                    'is_historical': True  # 과거 데이터임을 표시
                }
            else:
                print(f"⚠️ 최근 데이터 없음: {data.get('msg1', '데이터 없음')}")
                # 실시간 데이터로 재시도
                return get_realtime_market_status(access_token, market_id)
        else:
            print(f"❌ 시장 상태 API HTTP 오류: {response.status_code}")
        return None
    except Exception as e:
        print(f"❌ [시장 상태 조회 오류]: {e}")
        return None


def get_realtime_market_status(access_token, market_id="0"):
    """실시간 시장 상태 조회 시도"""
    PATH = "/uapi/domestic-stock/v1/quotations/inquire-index"
    URL = URL_BASE + PATH
    
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {access_token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKUP03500100"
    }
    
    params = {
        "FID_COND_MRKT_DIV_CODE": market_id,
        "FID_INPUT_ISCD": "0001" if market_id == "0" else "1001"
    }
    
    try:
        response = requests.get(URL, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('rt_cd') == '0' and 'output' in data:
                market_data = data['output']
                return {
                    'index_name': market_data.get('hts_kor_isnm', ''),
                    'current_index': float(market_data.get('stck_prpr', '0')),
                    'volume': int(market_data.get('acml_vol', '0')),
                    'value': float(market_data.get('acml_tr_pbmn', '0')),
                    'change_rate': float(market_data.get('prdy_ctrt', '0')),
                    'trade_date': market_data.get('stck_bsop_date', ''),
                    'is_historical': False  # 실시간 데이터임을 표시
                }
        return None
    except Exception as e:
        print(f"❌ [실시간 시장 상태 조회 오류]: {e}")
        return None


def print_market_status(access_token):
    """코스피와 코스닥의 시장 상태를 출력합니다."""
    print("\n🔍 시장 상태 조회를 시작합니다...")
    
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"📅 오늘 날짜: {today}")
    print(f"📊 최근 영업일: {get_previous_business_day()}")
    
    # 코스피 시장 상태 조회
    kospi_status = get_market_status(access_token, "0")
    if kospi_status:
        print("\n" + "="*60)
        data_type = "📜 [과거 데이터]" if kospi_status.get('is_historical') else "🔄 [실시간 데이터]"
        print(f"📈 {kospi_status['index_name']} 시장 현황 {data_type}")
        print("="*60)
        print(f"📅 거래일자: {kospi_status['trade_date']}")
        print(f"📊 현재 지수: {kospi_status['current_index']:,.2f}")
        print(f"📈 등락률: {kospi_status['change_rate']:+.2f}%")
        print(f"🔢 거래량: {kospi_status['volume']:,}주")
        print(f"💰 거래대금: {kospi_status['value']:,.0f}원")
    else:
        print("❌ 코스피 시장 상태 조회 실패 - 시장이 휴장 중일 수 있습니다")

    # 코스닥 시장 상태 조회
    kosdaq_status = get_market_status(access_token, "1")
    if kosdaq_status:
        print("\n" + "="*60)
        data_type = "📜 [과거 데이터]" if kosdaq_status.get('is_historical') else "🔄 [실시간 데이터]"
        print(f"📈 {kosdaq_status['index_name']} 시장 현황 {data_type}")
        print("="*60)
        print(f"📅 거래일자: {kosdaq_status['trade_date']}")
        print(f"📊 현재 지수: {kosdaq_status['current_index']:,.2f}")
        print(f"📈 등락률: {kosdaq_status['change_rate']:+.2f}%")
        print(f"🔢 거래량: {kosdaq_status['volume']:,}주")
        print(f"💰 거래대금: {kosdaq_status['value']:,.0f}원")
        print("="*60)
    else:
        print("❌ 코스닥 시장 상태 조회 실패 - 시장이 휴장 중일 수 있습니다")


# =========================================================
# --- 4. 위탁계좌(일반 주식계좌) 잔고 조회 ---
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
# --- 5. 메인 실행 블록 ---
# =========================================================

if __name__ == "__main__":
    print("🚀 한국투자증권 통합 조회 프로그램 시작")
    print(f"📁 토큰 파일: {TOKEN_FILE}")
    print(f"👤 계좌번호: {CANO}-{ACNT_PRDT_CD}")
    
    # 토큰 관리 시스템을 통해 유효한 토큰을 가져옵니다.
    final_token = get_token_for_api() 
    
    if final_token:
        print(f"🔑 토큰 획득 성공: {final_token[:30]}...")
        
        # 1. 시장 상태 조회 (공휴일에도 최근 데이터 표시)
        print_market_status(final_token)
        
        # 2. 위탁계좌 잔고 조회
        result = get_deposit_balance(final_token, APP_KEY, CANO, ACNT_PRDT_CD)
        
        if result:
            print("\n🎉 모든 조회가 완료되었습니다.")
            print("✅ 프로그램이 정상적으로 작동하고 있습니다!")
        else:
            print("\n❌ 위탁계좌 조회에 실패했습니다.")
    else:
        print("💥 프로그램을 종료합니다. 유효한 토큰을 확보하지 못했함. ")