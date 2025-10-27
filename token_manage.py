"""
token_manage.py: 한국투자증권 OpenAPI 토큰 관리 전용 모듈
- token-expire.json을 확인하여 유효하면 재사용
- 유효하지 않으면 새 토큰 발급 후 파일 업데이트

사용 예:
    from token_manage import get_token_for_api
    token = get_token_for_api(APP_KEY, APP_SECRET, URL_BASE)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import requests


TOKEN_FILE = "token-expire.json"
SECURITY_MARGIN = 60 * 10  # 만료 10분 전이면 갱신


def _save_new_token(app_key: str,
                    app_secret: str,
                    url_base: str,
                    token_file: str = TOKEN_FILE) -> Optional[str]:
    """API에 토큰을 요청하고 성공 시 파일에 저장 후 토큰 문자열을 반환"""
    PATH = "/oauth2/tokenP"
    url = url_base + PATH

    headers = {"Content-Type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret,
    }

    print("🔄 새 접근 토큰 발급을 시도합니다...")
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        if res.status_code != 200:
            print(f"❌ [토큰 발급 실패] 코드: {res.status_code}, 메시지: {res.text}")
            return None

        data = res.json()
        access_token = data.get("access_token")
        if not access_token:
            print(f"❌ [토큰 발급 실패] 응답에 access_token 없음: {data}")
            return None

        expires_in = int(data.get("expires_in", 86400))

        now_utc = datetime.now(timezone.utc)
        expiry_utc = now_utc + timedelta(seconds=expires_in)
        KST = timezone(timedelta(hours=9))
        expiry_kst = expiry_utc.astimezone(KST)

        token_data = {
            "access_token": access_token,
            "expires_in": expires_in,
            "expiry_timestamp_utc": expiry_utc.timestamp(),
            "expiry_datetime_kst": expiry_kst.strftime("%Y-%m-%d %H:%M:%S"),
        }

        with open(token_file, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=4)

        print(f"✅ [토큰 갱신 성공] KST 만료 시각: {token_data['expiry_datetime_kst']}")
        return access_token
    except requests.exceptions.RequestException as e:
        print(f"❌ [API 통신 오류] 토큰 발급 실패: {e}")
        return None
    except Exception as e:
        print(f"❌ [처리 오류] 토큰 저장/처리 중 오류: {e}")
        return None


def _get_token_from_file(token_file: str = TOKEN_FILE,
                         security_margin: int = SECURITY_MARGIN) -> Optional[str]:
    """저장된 파일에서 토큰을 읽어 유효하면 반환, 아니면 None"""
    if not os.path.exists(token_file):
        print("📄 [토큰 파일 없음] 저장된 토큰 파일이 없습니다.")
        return None

    try:
        with open(token_file, "r", encoding="utf-8") as f:
            token_data = json.load(f)
    except Exception as e:
        print(f"❌ [토큰 파일 읽기 오류]: {e}")
        return None

    access_token = token_data.get("access_token")
    expiry_ts = float(token_data.get("expiry_timestamp_utc", 0))
    expiry_kst = token_data.get("expiry_datetime_kst", "알 수 없음")

    if not access_token:
        print("❌ [토큰 없음] 저장된 파일에 access_token이 없습니다.")
        return None

    now_ts = time.time()
    if now_ts < expiry_ts - security_margin:
        print(f"✅ [토큰 재사용] 저장된 토큰이 유효합니다. (만료: {expiry_kst})")
        return access_token
    else:
        print(f"⚠️ [토큰 만료 임박] 저장된 토큰이 만료되었거나 곧 만료됩니다. (만료: {expiry_kst})")
        return None


def get_token_for_api(app_key: str,
                      app_secret: str,
                      url_base: str,
                      token_file: str = TOKEN_FILE,
                      security_margin: int = SECURITY_MARGIN) -> Optional[str]:
    """유효한 토큰을 반환. 필요시 자동 갱신."""
    token = _get_token_from_file(token_file=token_file, security_margin=security_margin)
    if token:
        return token
    print("🔄 토큰 갱신이 필요하여 새 토큰을 발급합니다...")
    return _save_new_token(app_key, app_secret, url_base, token_file)


def ensure_valid_token(app_key: str,
                       app_secret: str,
                       url_base: str,
                       token_file: str = TOKEN_FILE,
                       security_margin: int = SECURITY_MARGIN) -> Tuple[Optional[str], str]:
    """토큰을 보장하여 반환하고 상태 문자열(reused|refreshed|failed)을 함께 반환"""
    token = _get_token_from_file(token_file=token_file, security_margin=security_margin)
    if token:
        return token, "reused"
    new_token = _save_new_token(app_key, app_secret, url_base, token_file)
    if new_token:
        return new_token, "refreshed"
    return None, "failed"


# ------------------------------
# CLI: 단계별 상태 출력용
# ------------------------------
if __name__ == "__main__":
    import argparse
    from datetime import timezone as _timezone
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description="토큰 상태 점검 및 (옵션) 갱신")
    parser.add_argument("--token-file", default=TOKEN_FILE, help=f"토큰 파일 경로 (기본: {TOKEN_FILE})")
    parser.add_argument("--security-margin", type=int, default=SECURITY_MARGIN, help="만료 여유(초), 기본 600")
    parser.add_argument("--refresh", action="store_true", help="유효하지 않으면 새 토큰을 발급")
    args = parser.parse_args()

    print("[토큰 상태 점검]")
    print(f"📁 토큰 파일: {args.token_file}")

    # 현재 시각
    now_utc_dt = datetime.now(_timezone.utc)
    KST = _timezone(timedelta(hours=9))
    now_kst_dt = now_utc_dt.astimezone(KST)
    print(f"⏱️ 현재 시각(UTC): {now_utc_dt.strftime('%Y-%m-%d %H:%M:%S')} / (KST): {now_kst_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🛟 보안 여유(SECURITY_MARGIN): {args.security_margin}초")

    # 파일에서 정보 로드 및 유효성 판단
    token = _get_token_from_file(token_file=args.token_file, security_margin=args.security_margin)

    # 토큰 상세 정보 출력
    if os.path.exists(args.token_file):
        try:
            with open(args.token_file, "r", encoding="utf-8") as f:
                token_data = json.load(f)
            expiry_ts = float(token_data.get("expiry_timestamp_utc", 0))
            expiry_utc_dt = datetime.fromtimestamp(expiry_ts, tz=_timezone.utc)
            expiry_kst_dt = expiry_utc_dt.astimezone(KST)
            remaining = expiry_ts - time.time()
            print(f"🗓️ 만료 시각(UTC): {expiry_utc_dt.strftime('%Y-%m-%d %H:%M:%S')} / (KST): {expiry_kst_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"⏳ 남은 시간(초): {int(remaining)} (여유 포함 유효 판정 기준: 남은 시간 > {args.security_margin})")
        except Exception as e:
            print(f"⚠️ 토큰 정보 읽기 오류: {e}")

    if token:
        print("✅ 현재 토큰은 (여유시간 기준) 유효합니다. 새 발급 불필요")
    else:
        print("⚠️ 현재 토큰은 유효하지 않습니다. (만료되었거나 여유시간 이내)")
        if args.refresh:
            print("🔄 옵션 --refresh 지정됨: 새 토큰 발급 시도")
            # .env에서 키/URL을 로드하여 갱신 시도 (b_account 의존 제거)
            try:
                load_dotenv()
                APP_KEY = os.getenv("APP_KEY")
                APP_SECRET = os.getenv("APP_SECRET")
                URL_BASE = os.getenv("URL_BASE", "https://openapi.koreainvestment.com:9443")

                if not APP_KEY or not APP_SECRET:
                    print("❌ .env에서 APP_KEY/APP_SECRET을 찾을 수 없습니다. .env 파일을 확인하세요.")
                else:
                    new_token, status = ensure_valid_token(APP_KEY, APP_SECRET, URL_BASE, token_file=args.token_file, security_margin=args.security_margin)
                    if status == "refreshed":
                        print("✅ 새 토큰 발급 및 저장 완료")
                    elif status == "reused":
                        print("ℹ️ 직전 단계에서 재사용 가능해졌습니다(경합 상황).")
                    else:
                        print("❌ 새 토큰 발급 실패")
            except Exception as e:
                print(f"❌ .env 로드/토큰 갱신 중 오류: {e}")
        else:
            print("ℹ️ --refresh 옵션을 사용하면 즉시 새 토큰 발급을 시도합니다.")
