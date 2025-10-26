import requests
import json
import time
from datetime import datetime, timedelta, timezone
import os

# --- 설정 변수 (실제 값으로 대체하세요) ---
APP_KEY = "PSlNipf3HHE97a1T7l03GXxaMiwCVTLNu625"
APP_SECRET = "U0zG3Htk6UUWliQaBSMBSvya92PqMEIKPjdmFSbjTUPyb9SPhtfmNPmfSLBpEQF5kZsYhJV8Uox1As8ahYCfOf/Y9YxVD//6vpNro0cc4V5QtlxtvdjWEVAvFzRIAv2Jya70HQVxdQm1fGOYERmaewtmM6p6BlTWgrenUvFyc5gS5QBzwEg="
URL_BASE = "https://openapi.koreainvestment.com:9443"
TOKEN_FILE = 'token-expire.json'


def get_and_save_new_token(app_key, app_secret):
    """
    한국투자증권 API에 접근 토큰을 요청하고, 성공 시 JSON 파일에 저장합니다.
    """
    PATH = "/oauth2/tokenP" 
    URL = URL_BASE + PATH

    HEADERS = {"content-type": "application/json"}
    BODY = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret
    }
    
    print("🔄 새 접근 토큰 발급을 시도합니다...")

    try:
        res = requests.post(URL, headers=HEADERS, data=json.dumps(BODY))
        
        # --- 1. API 응답 확인 ---
        if res.status_code != 200:
            print(f"❌ [토큰 발급 실패] 응답 코드: {res.status_code}")
            print(f"   -> 오류 메시지: {res.text}")
            return False

        # --- 2. 토큰 정보 추출 및 계산 ---
        response_data = res.json()
        
        ACCESS_TOKEN = response_data['access_token']
        EXPIRES_IN_SECONDS = response_data.get('expires_in', 86400) # 기본 24시간
        
        # 현재 UTC 시각을 기준으로 만료 시점을 계산합니다.
        now_utc = datetime.now(timezone.utc)
        expiry_utc = now_utc + timedelta(seconds=EXPIRES_IN_SECONDS)
        
        # KST (한국 표준시, UTC + 9시간)로 변환하여 저장
        KST = timezone(timedelta(hours=9))
        expiry_kst = expiry_utc.astimezone(KST)

        # 파일에 저장할 데이터 구조
        token_data = {
            "access_token": ACCESS_TOKEN,
            "expires_in": EXPIRES_IN_SECONDS,
            "expiry_timestamp_utc": expiry_utc.timestamp(),
            "expiry_datetime_kst": expiry_kst.strftime("%Y-%m-%d %H:%M:%S")
        }

        # --- 3. 파일에 저장 ---
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(token_data, f, indent=4)
        
        print(f"✅ [토큰 발급 및 저장 성공] 새로운 토큰이 발급되어 {TOKEN_FILE}에 저장되었습니다.")
        print(f"   -> 발급된 토큰: {ACCESS_TOKEN[:20]}...")
        print(f"   -> KST 만료 시각: {token_data['expiry_datetime_kst']}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ [요청 오류] API 통신 중 오류 발생: {e}")
        return False
    except Exception as e:
        print(f"❌ [처리 오류] 데이터 처리 중 오류 발생: {e}")
        return False

# --- 함수 실행 ---
if __name__ == "__main__":
    # 실제 APP_KEY와 APP_SECRET을 넣어 실행하세요.
    get_and_save_new_token(APP_KEY, APP_SECRET)