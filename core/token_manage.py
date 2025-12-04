import os
import json
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta

# --- 경로 설정 (중요) ---
# 현재 파일(Token_manage.py)의 위치: .../hantu/core/
# 우리가 원하는 토큰 파일 위치: .../hantu/access_token.json (상위 폴더)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(BASE_DIR, 'access_token.json')
ENV_FILE = os.path.join(BASE_DIR, '.env')

# .env 파일 로드 (명시적 경로 지정)
load_dotenv(ENV_FILE)

# --- 설정값 ---
TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
MIN_VALID_TIME = 600  # 토큰이 10분 미만 남았으면 재발급

class TokenManager:
    def __init__(self):
        # 1. .env 파일에서 키 로드
        self.app_key = os.getenv("APP_KEY")
        self.app_secret = os.getenv("APP_SECRET")
        self.trading_mode = os.getenv("TRADING_MODE", "VIRTUAL") # 기본값 모의투자

        if not self.app_key or not self.app_secret:
            raise ValueError(f".env 파일({ENV_FILE})에서 APP_KEY/SECRET을 찾을 수 없습니다.")

        # 2. 거래 모드 설정
        if self.trading_mode == 'REAL':
            self.BASE_URL = "https://openapi.koreainvestment.com:9443"
            print(f"[설정] 실전 투자(REAL) 모드로 동작합니다.")
        else:
            self.BASE_URL = "https://openapivts.koreainvestment.com:29443"
            print(f"[설정] 모의 투자(VIRTUAL) 모드로 동작합니다.")
        
        self.TOKEN_URL = "/oauth2/tokenP"

    # 3. 토큰 파일 읽기
    def _read_token_info(self):
        if not os.path.exists(TOKEN_FILE):
            return None
        
        try:
            with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"[에러] 토큰 파일 읽기 실패: {e}")
            return None

    # 4. 유효성 검사
    def _is_token_valid(self, expiry_time_str):
        try:
            expiry_time = datetime.strptime(expiry_time_str, TIME_FORMAT)
            now = datetime.now()
            seconds_left = (expiry_time - now).total_seconds()

            if seconds_left > MIN_VALID_TIME:
                return True
            else:
                print(f"[알림] 토큰 만료 임박 또는 만료됨. (남은 시간: {int(seconds_left)}초)")
                return False
        except ValueError:
            return False

    # 5. 새 토큰 발급
    def _get_new_token(self):
        url = self.BASE_URL + self.TOKEN_URL
        headers = {"content-type": "application/json"}
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            print(f"[요청] 새 접근 토큰 발급을 요청합니다...")
            res = requests.post(url, headers=headers, data=json.dumps(payload))
            res.raise_for_status()
            token_data = res.json()
            
            # expires_in은 초 단위 (보통 86400초 = 24시간)
            expires_in = token_data.get('expires_in', 86400)
            new_expiry_time = datetime.now() + timedelta(seconds=expires_in)
            
            save_data = {
                "access_token": token_data.get('access_token'),
                "token_expired_time": new_expiry_time.strftime(TIME_FORMAT),
                "token_type": token_data.get('token_type', 'Bearer')
            }
            return save_data
            
        except Exception as e:
            print(f"[치명적 에러] 토큰 발급 실패: {e}")
            # .env 설정이나 네트워크 문제일 가능성 높음
            return None

    # 6. 토큰 저장
    def _save_token_info(self, token_data):
        try:
            with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, indent=4)
            print(f"[완료] 새 토큰이 {TOKEN_FILE} 에 저장되었습니다.")
        except IOError as e:
            print(f"[에러] 파일 저장 실패: {e}")

    # 7. 메인 실행 함수
    def manage_token(self):
        token_info = self._read_token_info()
        
        # 토큰이 있고 유효하면 그대로 반환
        if token_info and self._is_token_valid(token_info.get('token_expired_time')):
            return token_info['access_token']
        
        # 아니면 새로 발급
        new_token_data = self._get_new_token()
        if new_token_data:
            self._save_token_info(new_token_data)
            return new_token_data['access_token']
        else:
            return None

if __name__ == '__main__':
    # 테스트 실행
    manager = TokenManager()
    token = manager.manage_token()
    
    if token:
        print("\n>>> 토큰 관리자 정상 작동 확인")
        print(f"Token: {token[:20]}..." + " (보안을 위해 뒷부분 생략)")
    else:
        print("\n>>> 토큰 발급 실패. .env 파일과 키 값을 확인하세요.")