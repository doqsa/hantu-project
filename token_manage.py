"""
token_manage.py: 한국투자증권 OpenAPI 토큰 및 웹소켓 키 통합 관리 모듈
- token-expire.json을 확인하여 유효하면 재사용
- 유효하지 않으면 새 토큰 발급 후 파일 업데이트 (기존 데이터 보존)

사용 예:
    from token_manage import get_token_for_api, get_websocket_key
    token = get_token_for_api(APP_KEY, APP_SECRET, URL_BASE)
    ws_key = get_websocket_key(APP_KEY, APP_SECRET, URL_BASE)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any

import requests

TOKEN_FILE = "token-expire.json"
SECURITY_MARGIN = 60 * 10  # 만료 10분 전이면 갱신

# -----------------------------------------------------------
# 내부 유틸리티: JSON 파일 읽기/쓰기 (병합 모드)
# -----------------------------------------------------------
def _load_json(file_path: str) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ JSON 로드 실패: {e}")
        return {}

def _update_json(file_path: str, new_data: Dict[str, Any]):
    """기존 데이터를 읽어와서 새 데이터와 병합 후 저장"""
    current_data = _load_json(file_path)
    current_data.update(new_data)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(current_data, f, indent=4, ensure_ascii=False)

# -----------------------------------------------------------
# 1. REST API 접근 토큰 (Access Token) 관리
# -----------------------------------------------------------
def _save_new_token(app_key: str, app_secret: str, url_base: str, token_file: str = TOKEN_FILE) -> Optional[str]:
    PATH = "/oauth2/tokenP"
    url = url_base + PATH
    headers = {"Content-Type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret,
    }

    print("🔄 [API] 새 접근 토큰 발급 시도...")
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        if res.status_code != 200:
            print(f"❌ [API] 발급 실패 코드: {res.status_code}, 메시지: {res.text}")
            return None

        data = res.json()
        access_token = data.get("access_token")
        expires_in = int(data.get("expires_in", 86400))

        now_utc = datetime.now(timezone.utc)
        expiry_utc = now_utc + timedelta(seconds=expires_in)
        KST = timezone(timedelta(hours=9))
        expiry_kst = expiry_utc.astimezone(KST)

        # 저장할 데이터 (기존 데이터 유지하면서 병합)
        token_data = {
            "access_token": access_token,
            "token_expires_in": expires_in,
            "token_expiry_ts": expiry_utc.timestamp(),
            "token_expiry_dt": expiry_kst.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _update_json(token_file, token_data)

        print(f"✅ [API] 토큰 갱신 완료 (만료: {token_data['token_expiry_dt']})")
        return access_token
    except Exception as e:
        print(f"❌ [API] 처리 오류: {e}")
        return None

def get_token_for_api(app_key: str, app_secret: str, url_base: str, token_file: str = TOKEN_FILE) -> Optional[str]:
    """유효한 REST API 토큰 반환"""
    data = _load_json(token_file)
    access_token = data.get("access_token")
    expiry_ts = float(data.get("token_expiry_ts", 0))

    if access_token and time.time() < expiry_ts - SECURITY_MARGIN:
        return access_token
    
    return _save_new_token(app_key, app_secret, url_base, token_file)


# -----------------------------------------------------------
# 2. 웹소켓 접속키 (WebSocket Key) 관리
# -----------------------------------------------------------
def _save_new_websocket_key(app_key: str, app_secret: str, url_base: str, token_file: str = TOKEN_FILE) -> Optional[str]:
    PATH = "/oauth2/Approval"
    url = url_base + PATH
    headers = {"content-type": "application/json; utf-8"}
    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "secretkey": app_secret,
    }

    print("🔄 [WS] 새 웹소켓 접속키 발급 시도...")
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        if res.status_code != 200:
            print(f"❌ [WS] 발급 실패 코드: {res.status_code}, 메시지: {res.text}")
            return None

        data = res.json()
        approval_key = data.get("approval_key")
        
        # 웹소켓 키는 명시적 만료시간을 안 주므로 하루(24시간)로 가정
        now_utc = datetime.now(timezone.utc)
        expiry_utc = now_utc + timedelta(hours=23) # 안전하게 23시간 설정
        KST = timezone(timedelta(hours=9))
        expiry_kst = expiry_utc.astimezone(KST)

        ws_data = {
            "websocket_key": approval_key,
            "ws_expiry_ts": expiry_utc.timestamp(),
            "ws_expiry_dt": expiry_kst.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _update_json(token_file, ws_data)

        print(f"✅ [WS] 키 갱신 완료 (만료예상: {ws_data['ws_expiry_dt']})")
        return approval_key
    except Exception as e:
        print(f"❌ [WS] 처리 오류: {e}")
        return None

def get_websocket_key(app_key: str, app_secret: str, url_base: str, token_file: str = TOKEN_FILE) -> Optional[str]:
    """유효한 웹소켓 접속키 반환"""
    data = _load_json(token_file)
    ws_key = data.get("websocket_key")
    expiry_ts = float(data.get("ws_expiry_ts", 0))

    # 웹소켓 키가 있고 유효기간이 남았으면 재사용
    if ws_key and time.time() < expiry_ts - SECURITY_MARGIN:
        return ws_key
    
    return _save_new_websocket_key(app_key, app_secret, url_base, token_file)


# -----------------------------------------------------------
# CLI: 상태 점검 및 테스트
# -----------------------------------------------------------
if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description="토큰 통합 관리자")
    parser.add_argument("--refresh", action="store_true", help="강제로 키를 새로 발급")
    args = parser.parse_args()

    print("📊 [토큰 정보 확인]")
    
    # 1. 파일 상태 확인
    if os.path.exists(TOKEN_FILE):
        data = _load_json(TOKEN_FILE)
        print(f"📁 파일: {TOKEN_FILE} (발견됨)")
        print(f"   - REST 만료: {data.get('token_expiry_dt', '없음')}")
        print(f"   - WS   만료: {data.get('ws_expiry_dt', '없음')}")
    else:
        print(f"📁 파일: {TOKEN_FILE} (없음 - 최초 실행 필요)")

    # 2. 강제 갱신 또는 테스트
    if args.refresh:
        load_dotenv() # .env 파일 로드
        APP_KEY = os.getenv("APP_KEY")
        APP_SECRET = os.getenv("APP_SECRET")
        # key.py에 있는 URL_BASE를 못 가져오면 기본값(실전) 사용
        URL_BASE = os.getenv("URL_BASE", "https://openapi.koreainvestment.com:9443")

        if APP_KEY and APP_SECRET:
            print("\n🚀 강제 갱신을 시작합니다...")
            get_token_for_api(APP_KEY, APP_SECRET, URL_BASE)
            get_websocket_key(APP_KEY, APP_SECRET, URL_BASE)
            print("✨ 모든 작업 완료.")
        else:
            print("❌ .env 파일에 APP_KEY, APP_SECRET이 설정되어야 테스트 가능합니다.")