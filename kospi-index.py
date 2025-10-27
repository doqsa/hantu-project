import os
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

import requests
from dotenv import load_dotenv

from token_manage import get_token_for_api


def fetch_kospi_period_price(token: str,
                             app_key: str,
                             app_secret: str,
                             url_base: str,
                             start_date: str,
                             end_date: str,
                             period_code: str = "D",
                             verbose: bool = True) -> List[Dict[str, Any]]:
    """
    KOSPI 지수 기간별 시세 조회 (일/주/월/년)

    - 기본값은 일봉(D)
    - FID_INPUT_ISCD="0001" 는 KOSPI 지수
    - 반환: [{date, open, high, low, close, volume} ...] 최근 날짜순 정렬
    """
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
        "FID_COND_MRKT_DIV_CODE": "U",    # 통합증권시장
        "FID_INPUT_ISCD": "0001",         # KOSPI 지수
        "FID_INPUT_DATE_1": start_date,    # 시작일자 YYYYMMDD
        "FID_INPUT_DATE_2": end_date,      # 종료일자 YYYYMMDD
        "FID_PERIOD_DIV_CODE": period_code,  # D/W/M/Y
        "FID_ORG_ADJ_PRC": "0",           # 수정주가 미적용
    }

    if verbose:
        print(f"📡 요청: {url}")
        print(f"   기간: {start_date} ~ {end_date}, 주기: {period_code}")

    res = requests.get(url, headers=headers, params=params, timeout=10)
    try:
        data = res.json()
    except Exception:
        data = {"raw": res.text}

    if res.status_code != 200:
        print(f"❌ HTTP {res.status_code} 오류: {data}")
        return []

    if str(data.get("rt_cd")) != "0":
        print(f"❌ API 오류: {data.get('msg1', '원인 불명')}")
        return []

    # output2에 캔들 데이터가 담기는 형태가 일반적
    candles = data.get("output2") or data.get("output") or []
    if not isinstance(candles, list):
        print("⚠️ 예상과 다른 응답 포맷:", data)
        return []

    def _to_int(s: Any) -> int:
        try:
            return int(str(s))
        except Exception:
            return 0

    def _to_float(s: Any) -> float:
        try:
            return float(str(s))
        except Exception:
            return 0.0

    result = []
    for row in candles:
        # 업종/지수 응답은 bstp_nmix_* 필드 사용 (dow.py 참고)
        date = row.get("stck_bsop_date")
        close = row.get("bstp_nmix_prpr")
        open_ = row.get("bstp_nmix_oprc")
        high = row.get("bstp_nmix_hgpr")
        low = row.get("bstp_nmix_lwpr")

        # 혹시 필드가 없으면 종목용 stck_*로 폴백
        if close is None:
            close = row.get("stck_clpr")
            open_ = row.get("stck_oprc") if open_ is None else open_
            high = row.get("stck_hgpr") if high is None else high
            low = row.get("stck_lwpr") if low is None else low

        result.append({
            "date": date,
            "open": _to_float(open_),
            "high": _to_float(high),
            "low": _to_float(low),
            "close": _to_float(close),
            "volume": _to_int(row.get("acml_vol")),
            "amount": _to_float(row.get("acml_tr_pbmn")),
        })

    # 최근 날짜가 앞에 오는 경우가 많으므로, 날짜 오름차순으로 정렬
    result.sort(key=lambda x: x["date"])  # YYYYMMDD 문자열 기준 정렬
    return result


def _yyyymmdd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


if __name__ == "__main__":
    load_dotenv()

    APP_KEY = os.getenv("APP_KEY")
    APP_SECRET = os.getenv("APP_SECRET")
    URL_BASE = os.getenv("URL_BASE", "https://openapi.koreainvestment.com:9443")

    if not APP_KEY or not APP_SECRET:
        print("❌ .env에 APP_KEY/APP_SECRET가 필요합니다. .env.example을 참고하세요.")
        raise SystemExit(1)

    token = get_token_for_api(APP_KEY, APP_SECRET, URL_BASE)
    if not token:
        print("❌ 유효한 토큰을 발급/확보하지 못했습니다.")
        raise SystemExit(1)

    # 최근 7거래일을 충분히 커버하기 위해 14일 전부터 어제까지 요청 (오늘 제외)
    # 테스트: 2년치 데이터 조회 (730일)
    KST = timezone(timedelta(hours=9))
    today_kst = datetime.now(KST)
    yesterday_kst = today_kst - timedelta(days=1)
    start_dt = yesterday_kst - timedelta(days=730)  # 2년
    start_str = _yyyymmdd(start_dt)
    end_str = _yyyymmdd(yesterday_kst)

    prices = fetch_kospi_period_price(token, APP_KEY, APP_SECRET, URL_BASE, start_str, end_str, period_code="D", verbose=False)

    if not prices:
        print("❌ 데이터를 가져오지 못했습니다.")
        raise SystemExit(1)

    print(f"\n📊 총 {len(prices)}일 데이터 조회됨")
    print(f"   첫 거래일: {prices[0]['date']}")
    print(f"   마지막 거래일: {prices[-1]['date']}")

    # 마지막 7개 (최근 7거래일)만 콘솔 출력
    last7 = prices[-7:]
    print("\n📈 최근 7거래일 KOSPI 지수 (일자 / 최고가 / 최저가 / 종가 / 거래량 / 거래대금)\n" + "-" * 92)
    
    # 요일 한글 매핑
    weekday_kr = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"]
    
    # 출력용 데이터 준비 (요일 포함)
    output_data = []
    
    for row in last7:
        ymd = row["date"]
        # YYYYMMDD를 datetime으로 변환하여 요일 계산
        try:
            dt = datetime.strptime(ymd, "%Y%m%d")
            day_of_week = weekday_kr[dt.weekday()]  # 0=월요일, 6=일요일
            date_with_dow = f"{ymd}{day_of_week}"
            weekday_only = day_of_week
        except Exception:
            date_with_dow = ymd
            weekday_only = ""
        
        high = row.get("high", 0.0)
        low = row.get("low", 0.0)
        close = row.get("close", 0.0)
        vol = row.get("volume", 0)
        amt = row.get("amount", 0.0)
        
        # 콘솔 출력
        print(f"{date_with_dow} | {high:>10,.2f} | {low:>10,.2f} | {close:>10,.2f} | {vol:>12,} | {amt:>14,.0f}")
        
        # JSON용 데이터 추가
        output_data.append({
            "date": ymd,
            "weekday": weekday_only,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
            "amount": amt
        })
    
    # JSON 파일로 저장 (전체 데이터)
    json_output = {
        "generated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "market": "KOSPI",
        "period_days": len(prices),
        "start_date": prices[0]["date"],
        "end_date": prices[-1]["date"],
        "data": []
    }
    
    # 전체 데이터를 JSON에 저장 (요일 포함)
    weekday_kr = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"]
    for row in prices:
        ymd = row["date"]
        try:
            dt = datetime.strptime(ymd, "%Y%m%d")
            weekday_only = weekday_kr[dt.weekday()]
        except Exception:
            weekday_only = ""
        
        json_output["data"].append({
            "date": ymd,
            "weekday": weekday_only,
            "high": row.get("high", 0.0),
            "low": row.get("low", 0.0),
            "close": row.get("close", 0.0),
            "volume": row.get("volume", 0),
            "amount": row.get("amount", 0.0)
        })
    
    json_filename = "kospi_index_data.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 전체 {len(prices)}일 데이터가 '{json_filename}' 파일로 저장되었습니다.")

    # 요약 출력은 생략
