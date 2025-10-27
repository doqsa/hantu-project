import os
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

import requests
from dotenv import load_dotenv

from token_manage import get_token_for_api


def fetch_kosdaq_period_price(token: str,
                              app_key: str,
                              app_secret: str,
                              url_base: str,
                              start_date: str,
                              end_date: str,
                              period_code: str = "D",
                              verbose: bool = True) -> List[Dict[str, Any]]:
    """
    KOSDAQ 지수 기간별 시세 조회 (일/주/월/년)

    - 기본값은 일봉(D)
    - FID_INPUT_ISCD="1001" 는 KOSDAQ 지수
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
        "FID_INPUT_ISCD": "1001",         # KOSDAQ 지수 (0001: KOSPI, 1001: KOSDAQ)
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
        # 업종/지수 응답은 bstp_nmix_* 필드 사용
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
    import time
    
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

    # 약 1000일 데이터를 50일씩 20회 조회
    KST = timezone(timedelta(hours=9))
    today_kst = datetime.now(KST)
    yesterday_kst = today_kst - timedelta(days=1)
    
    iterations = 20
    chunk_size = 50  # API 제한: 최대 50일
    
    all_prices = []
    current_end = yesterday_kst
    
    print(f"📊 KOSDAQ 데이터 조회 시작 (50일씩 {iterations}회)")
    print(f"   예상 커버 기간: 약 {iterations * chunk_size}일\n")
    
    for i in range(iterations):
        chunk_start = current_end - timedelta(days=chunk_size)
        start_str = _yyyymmdd(chunk_start)
        end_str = _yyyymmdd(current_end)
        
        print(f"[{i+1}/{iterations}] 조회 중: {start_str} ~ {end_str}", end=" ")
        
        chunk_data = fetch_kosdaq_period_price(
            token, APP_KEY, APP_SECRET, URL_BASE,
            start_str, end_str,
            period_code="D",
            verbose=False
        )
        
        if chunk_data:
            all_prices.extend(chunk_data)
            print(f"✅ {len(chunk_data)}일")
        else:
            print(f"❌ 실패")
            break
        
        # 다음 구간으로 이동
        current_end = chunk_start - timedelta(days=1)
        
        # API 호출 제한 방지: 0.5초 대기
        if i < iterations - 1:  # 마지막 호출 후에는 대기 불필요
            time.sleep(0.5)
    
    # 날짜 중복 제거 및 정렬
    unique_prices = {}
    for item in all_prices:
        date = item["date"]
        if date not in unique_prices:
            unique_prices[date] = item
    
    prices = sorted(unique_prices.values(), key=lambda x: x["date"])
    
    if not prices:
        print("\n❌ 데이터를 가져오지 못했습니다.")
        raise SystemExit(1)

    print(f"\n📊 API로부터 {len(prices)}일 데이터 조회 완료")
    print(f"   첫 거래일: {prices[0]['date']}")
    print(f"   마지막 거래일: {prices[-1]['date']}")
    
    json_filename = "kosdaq_index_data.json"
    
    # 기존 JSON 파일 로드 (있으면)
    existing_data = {}
    if os.path.exists(json_filename):
        try:
            with open(json_filename, "r", encoding="utf-8") as f:
                existing_json = json.load(f)
                for item in existing_json.get("data", []):
                    existing_data[item["date"]] = item
            print(f"\n📂 기존 파일 발견: {len(existing_data)}일 데이터 로드됨")
        except Exception as e:
            print(f"\n⚠️ 기존 파일 읽기 오류: {e}")
            print("   새 파일로 저장합니다.")
    
    # 새 데이터와 기존 데이터 병합 (중복 날짜는 새 데이터로 덮어쓰기)
    weekday_kr = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"]
    
    new_count = 0
    updated_count = 0
    
    for row in prices:
        ymd = row["date"]
        try:
            dt = datetime.strptime(ymd, "%Y%m%d")
            weekday_only = weekday_kr[dt.weekday()]
        except Exception:
            weekday_only = ""
        
        new_item = {
            "date": ymd,
            "weekday": weekday_only,
            "high": row.get("high", 0.0),
            "low": row.get("low", 0.0),
            "close": row.get("close", 0.0),
            "volume": row.get("volume", 0),
            "amount": row.get("amount", 0.0)
        }
        
        if ymd in existing_data:
            # 기존 데이터 갱신
            existing_data[ymd] = new_item
            updated_count += 1
        else:
            # 새 데이터 추가
            existing_data[ymd] = new_item
            new_count += 1
    
    # 날짜 순으로 정렬하여 최종 데이터 구성
    final_data = sorted(existing_data.values(), key=lambda x: x["date"])
    
    # JSON 파일로 저장
    json_output = {
        "generated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "market": "KOSDAQ",
        "period_days": len(final_data),
        "start_date": final_data[0]["date"],
        "end_date": final_data[-1]["date"],
        "data": final_data
    }
    
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 '{json_filename}' 파일 업데이트 완료")
    print(f"   📊 전체 데이터: {len(final_data)}일")
    print(f"   🆕 새로 추가: {new_count}일")
    print(f"   🔄 갱신됨: {updated_count}일")
    print(f"   📅 기간: {final_data[0]['date']} ~ {final_data[-1]['date']}")
