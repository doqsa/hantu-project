"""
test_2year_fetch.py: 2년치 코스피 일별 데이터 조회 가능 여부 테스트
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import requests
from dotenv import load_dotenv
from token_manage import get_token_for_api

load_dotenv()

def fetch_kospi_period_price(token, app_key, app_secret, url_base, start_date, end_date, period_code="D", verbose=True):
    """코스피 일별 시세 간단 조회"""
    path = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
    url = url_base + path
    
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "FHKUP03500100",
    }
    
    params = {
        "FID_COND_MRKT_DIV_CODE": "U",
        "FID_INPUT_ISCD": "0001",
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
        "FID_PERIOD_DIV_CODE": period_code,
        "FID_ORG_ADJ_PRC": "0",
    }
    
    if verbose:
        print(f"📡 요청: {url}")
        print(f"   기간: {start_date} ~ {end_date}")
    
    res = requests.get(url, headers=headers, params=params, timeout=10)
    data = res.json()
    
    if res.status_code != 200 or str(data.get("rt_cd")) != "0":
        print(f"❌ 오류: {data.get('msg1', 'Unknown')}")
        return []
    
    candles = data.get("output2") or data.get("output") or []
    
    result = []
    for row in candles:
        result.append({
            "date": row.get("stck_bsop_date"),
            "close": float(row.get("bstp_nmix_prpr", 0)),
        })
    
    result.sort(key=lambda x: x["date"])
    return result


APP_KEY = os.getenv("APP_KEY")
APP_SECRET = os.getenv("APP_SECRET")
URL_BASE = os.getenv("URL_BASE", "https://openapi.koreainvestment.com:9443")

if not APP_KEY or not APP_SECRET:
    print("❌ .env에 APP_KEY/APP_SECRET가 필요합니다.")
    exit(1)

token = get_token_for_api(APP_KEY, APP_SECRET, URL_BASE)
if not token:
    print("❌ 토큰 발급 실패")
    exit(1)

KST = timezone(timedelta(hours=9))
yesterday = datetime.now(KST) - timedelta(days=1)

# 2년 전부터 어제까지
start_2y = yesterday - timedelta(days=730)  # 2년 = 730일
start_str = start_2y.strftime("%Y%m%d")
end_str = yesterday.strftime("%Y%m%d")

print(f"📊 2년치 데이터 조회 테스트")
print(f"   기간: {start_str} ~ {end_str} (약 730일)")
print(f"   요청 중...\n")

# 실제 조회
prices = fetch_kospi_period_price(
    token, APP_KEY, APP_SECRET, URL_BASE,
    start_str, end_str,
    period_code="D",
    verbose=True
)

if prices:
    print(f"\n✅ 성공: {len(prices)}일 데이터 조회됨")
    print(f"   첫 날짜: {prices[0]['date']}")
    print(f"   마지막 날짜: {prices[-1]['date']}")
    print(f"   실제 거래일 수: {len(prices)}일")
    print(f"\n💡 2년치 데이터 조회 가능합니다!")
else:
    print(f"\n❌ 조회 실패 - API 제한 또는 오류")
    print(f"   더 짧은 기간으로 시도하거나 주봉/월봉 사용을 고려하세요.")
