import requests
import json
import datetime
import os

# 토큰 및 키를 저장할 파일명
TOKEN_FILE = "token-expire.json"

def save_token_info(data):
    """토큰 정보를 JSON 파일로 저장"""
    with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_token_info():
    """파일에서 토큰 정보 읽기"""
    if not os.path.exists(TOKEN_FILE):
        return {}
    
    try:
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

# =========================================================
# 1. 기존 REST API 토큰 관리 (그대로 유지)
# =========================================================
def get_token_for_api(app_key, app_secret, url_base):
    saved_info = load_token_info()
    
    # 저장된 토큰이 있고, 유효기간이 남았는지 확인
    if "access_token" in saved_info and "token_expired" in saved_info:
        expire_time = datetime.datetime.strptime(saved_info["token_expired"], "%Y-%m-%d %H:%M:%S")
        if datetime.datetime.now() < expire_time:
            return saved_info["access_token"]
            
    # 유효하지 않으면 새로 발급
    print("🔄 API 토큰 새로 발급 중...")
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret
    }
    url = f"{url_base}/oauth2/tokenP"
    res = requests.post(url, headers=headers, data=json.dumps(body))
    
    if res.status_code == 200:
        data = res.json()
        access_token = data['access_token']
        # 유효기간: 현재시간 + (expires_in - 60초 여유)
        expired_dt = datetime.datetime.now() + datetime.timedelta(seconds=int(data['expires_in']) - 60)
        
        # 정보 업데이트
        saved_info["access_token"] = access_token
        saved_info["token_expired"] = expired_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        save_token_info(saved_info)
        return access_token
    else:
        print(f"❌ 토큰 발급 실패: {res.text}")
        return None

# =========================================================
# 2. [추가됨] 웹소켓 접속키 관리
# =========================================================
def get_websocket_key(app_key, app_secret, url_base):
    saved_info = load_token_info()
    
    # 저장된 키가 있고, 유효기간이 남았는지 확인 (웹소켓 키도 24시간 정도로 관리)
    if "websocket_key" in saved_info and "socket_expired" in saved_info:
        expire_time = datetime.datetime.strptime(saved_info["socket_expired"], "%Y-%m-%d %H:%M:%S")
        if datetime.datetime.now() < expire_time:
            # print("✅ 기존 웹소켓 키 사용") # 너무 자주 뜨면 주석 처리
            return saved_info["websocket_key"]
            
    # 없으면 새로 발급
    print("🔄 웹소켓 접속키 새로 발급 중...")
    headers = {"content-type": "application/json; utf-8"}
    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "secretkey": app_secret
    }
    url = f"{url_base}/oauth2/Approval"
    res = requests.post(url, headers=headers, data=json.dumps(body))
    
    if res.status_code == 200:
        data = res.json()
        approval_key = data['approval_key']
        
        # 웹소켓 키는 명시적 유효기간을 안 주지만, 보통 24시간 안전하게 잡음
        expired_dt = datetime.datetime.now() + datetime.timedelta(hours=23)
        
        # 정보 업데이트
        saved_info["websocket_key"] = approval_key
        saved_info["socket_expired"] = expired_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        save_token_info(saved_info)
        return approval_key
    else:
        print(f"❌ 웹소켓 키 발급 실패: {res.text}")
        return None