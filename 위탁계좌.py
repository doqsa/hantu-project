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
# --- 3. 잔고 조회 API 함수 정의 ---
# =========================================================

def get_account_balance(token, app_key, cano, acnt_prdt_cd):
    """
    유효한 토큰을 사용하여 계좌 잔고 정보를 조회합니다.
    """
    PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
    URL = URL_BASE + PATH
    
    # 여러 TR_ID 시도 (실전투자)
    TR_IDS = ["TTTC8434R", "TTTC8498R", "CTPC8434R"]
    
    for tr_id in TR_IDS:
        print(f"\n🔍 계좌 잔고 조회를 시도합니다... (TR_ID: {tr_id})")
        
        HEADERS = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": app_key,
            "appsecret": APP_SECRET,
            "tr_id": tr_id
        }
        
        # 다양한 파라미터 조합 시도
        PARAMS_COMBINATIONS = [
            # 조회구분 00 + 단가구분 01
            {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "00",  # 전체조회
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": ""
            },
            # 조회구분 01 + 단가구분 01
            {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "01",  # 종목조회
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": ""
            },
            # 간단한 파라미터
            {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "INQR_DVSN": "00",
                "UNPR_DVSN": "01"
            }
        ]
        
        for i, params in enumerate(PARAMS_COMBINATIONS, 1):
            print(f"   파라미터 조합 {i} 시도...")
            
            try:
                res = requests.get(URL, headers=HEADERS, params=params, timeout=10)
                response_data = res.json()
                
                print(f"   📡 응답 상태: {res.status_code}")
                
                if res.status_code == 200 and response_data.get('rt_cd') == '0':
                    balance_data = response_data
                    
                    print(f"✅ [잔고 조회 성공] TR_ID: {tr_id}, 파라미터: {i}")
                    print("=" * 60)
                    
                    # 상세한 응답 데이터 출력
                    print(f"📋 전체 응답 구조:")
                    for key in response_data.keys():
                        if key in ['output1', 'output2']:
                            item_count = len(response_data[key]) if response_data[key] else 0
                            print(f"   - {key}: {item_count}개 항목")
                        else:
                            print(f"   - {key}: {response_data[key]}")
                    
                    print("\n💰 잔고 정보:")
                    # output2 (예수금 정보) 출력
                    if balance_data.get('output2') and len(balance_data['output2']) > 0:
                        cash_info = balance_data['output2'][0]
                        print("   [예수금 정보]")
                        for key, value in cash_info.items():
                            print(f"     {key}: {value}")
                    
                    # output1 (주식 보유 내역) 출력
                    if balance_data.get('output1'):
                        print(f"\n   [보유 주식] {len(balance_data['output1'])}개 종목")
                        for i, stock in enumerate(balance_data['output1'], 1):
                            if int(stock.get('hldg_qty', 0)) > 0:
                                print(f"   {i:2d}. {stock.get('prdt_name', 'N/A')}")
                                print(f"       종목코드: {stock.get('pdno', 'N/A')}")
                                print(f"       보유수량: {stock.get('hldg_qty', 0):>8} 주")
                                print(f"       평균단가: {stock.get('pchs_avg_pric', 0):>8} 원")
                                print(f"       현재가: {stock.get('prpr', 0):>8} 원")
                                print(f"       평가금액: {stock.get('evlu_amt', 0):>8} 원")
                                print(f"       평가손익: {stock.get('evlu_pfls_amt', 0):>8} 원")
                    else:
                        print("\n   📊 보유 주식이 없습니다.")
                    
                    print("=" * 60)
                    return balance_data
                else:
                    print(f"   ❌ 파라미터 {i} 실패: {response_data.get('msg_cd', 'N/A')} - {response_data.get('msg1', 'API 오류')}")
                    
            except requests.exceptions.RequestException as e:
                print(f"   ❌ [통신 오류] {e}")
            except Exception as e:
                print(f"   ❌ [처리 오류] {e}")
    
    print("❌ [잔고 조회 실패] 모든 TR_ID와 파라미터 조합에서 실패했습니다.")
    return None


# =========================================================
# --- 4. 메인 실행 블록 ---
# =========================================================

if __name__ == "__main__":
    print("🚀 한국투자증권 API 잔고 조회 프로그램 시작")
    print(f"📁 토큰 파일: {TOKEN_FILE}")
    print(f"👤 계좌번호: {CANO}-{ACNT_PRDT_CD}")
    
    # 토큰 관리 시스템을 통해 유효한 토큰을 가져옵니다.
    final_token = get_token_for_api() 
    
    if final_token:
        print(f"🔑 토큰 획득 성공: {final_token[:30]}...")
        # 유효한 토큰으로 잔고 조회 API를 호출합니다.
        result = get_account_balance(final_token, APP_KEY, CANO, ACNT_PRDT_CD)
        
        if result:
            print("🎉 프로그램이 성공적으로 완료되었습니다.")
        else:
            print("❌ 잔고 조회에 실패했습니다.")
    else:
        print("💥 프로그램을 종료합니다. 유효한 토큰을 확보하지 못했습니다.")