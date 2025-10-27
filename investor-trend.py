"""
investor-trend.py: 시장별 투자자 매매동향 (일별) 조회
- 코스피/코스닥 시장의 개인/외국인/기관 등 투자자별 순매수 추이
- API: /uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market
- 참고: 모의투자 미지원 - 실전투자 계정 필요
"""

import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

import requests
from dotenv import load_dotenv

from token_manage import get_token_for_api


def fetch_investor_trend_daily(token: str,
                                app_key: str,
                                app_secret: str,
                                url_base: str,
                                market_code: str = "J",
                                start_date: str = None,
                                end_date: str = None,
                                verbose: bool = True) -> List[Dict[str, Any]]:
    """
    시장별 투자자 매매동향 (일별) 조회

    Args:
        token: 인증 토큰
        app_key: APP KEY
        app_secret: APP SECRET
        url_base: API base URL
        market_code: 시장구분 (J:코스피, Q:코스닥, 기본값: J)
        start_date: 조회 시작일 YYYYMMDD (미지정시 최근 30일 전)
        end_date: 조회 종료일 YYYYMMDD (미지정시 어제)
        verbose: 상세 로그 출력 여부

    Returns:
        list: 일자별 투자자 매매동향 데이터
    """
    path = "/uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market"
    url = url_base + path

    # 기본 기간 설정 (어제부터 최근 30일)
    if not end_date or not start_date:
        KST = timezone(timedelta(hours=9))
        yesterday = datetime.now(KST) - timedelta(days=1)
        end_date = yesterday.strftime("%Y%m%d")
        start_date = (yesterday - timedelta(days=30)).strftime("%Y%m%d")

    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "FHPTJ04400000",  # 시장별 투자자매매동향(일별)
    }

    params = {
        "FID_COND_MRKT_DIV_CODE": market_code,  # J:코스피, Q:코스닥
        "FID_INPUT_ISCD": "0000",  # 전체 (시장별 조회시 고정값)
        "FID_INPUT_DATE_1": start_date,  # 조회 시작일
        "FID_INPUT_DATE_2": end_date,    # 조회 종료일
        "FID_PERIOD_DIV_CODE": "D",      # D:일별
    }

    if verbose:
        market_name = "코스피" if market_code == "J" else "코스닥" if market_code == "Q" else market_code
        print(f"\n📊 [{market_name} 투자자 매매동향 조회]")
        print(f"   기간: {start_date} ~ {end_date}")

    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        
        if verbose:
            print(f"   응답 코드: {res.status_code}")
        
        if res.status_code != 200:
            if verbose:
                print(f"❌ HTTP {res.status_code} 오류")
                print(f"   응답: {res.text[:500]}")
            return []

        data = res.json()

        if str(data.get("rt_cd")) != "0":
            if verbose:
                print(f"❌ API 오류: {data.get('msg1', '원인 불명')} (코드: {data.get('rt_cd')})")
                print(f"   메시지: {data.get('msg_cd', 'N/A')}")
            return []

        output = data.get("output") or []
        
        if verbose:
            print(f"✅ 조회 성공: {len(output)}일 데이터")

        result = []
        for row in output:
            # 투자자별 순매수 금액 (단위: 원, 양수=순매수/음수=순매도)
            result.append({
                "date": row.get("stck_bsop_date"),  # 영업일자
                "individual": int(row.get("prsn_ntby_qty", 0)),  # 개인 순매수량
                "individual_amt": int(row.get("prsn_ntby_tr_pbmn", 0)),  # 개인 순매수대금
                "foreign": int(row.get("frgn_ntby_qty", 0)),  # 외국인 순매수량
                "foreign_amt": int(row.get("frgn_ntby_tr_pbmn", 0)),  # 외국인 순매수대금
                "institution": int(row.get("orgn_ntby_qty", 0)),  # 기관 순매수량
                "institution_amt": int(row.get("orgn_ntby_tr_pbmn", 0)),  # 기관 순매수대금
            })

        # 날짜 오름차순 정렬
        result.sort(key=lambda x: x["date"])
        return result

    except requests.exceptions.RequestException as e:
        if verbose:
            print(f"❌ 네트워크 오류: {e}")
        return []
    except Exception as e:
        if verbose:
            print(f"❌ 처리 오류: {e}")
        return []


def _yyyymmdd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


if __name__ == "__main__":
    load_dotenv()

    APP_KEY = os.getenv("APP_KEY")
    APP_SECRET = os.getenv("APP_SECRET")
    URL_BASE = os.getenv("URL_BASE", "https://openapi.koreainvestment.com:9443")

    if not APP_KEY or not APP_SECRET:
        print("❌ .env에 APP_KEY/APP_SECRET가 필요합니다.")
        raise SystemExit(1)

    print("⚠️  주의: 이 API는 모의투자 미지원입니다. 실전투자 계정 필요.")
    
    token = get_token_for_api(APP_KEY, APP_SECRET, URL_BASE)
    if not token:
        print("❌ 유효한 토큰을 발급받지 못했습니다.")
        raise SystemExit(1)

    # 최근 7거래일 투자자 동향 조회
    KST = timezone(timedelta(hours=9))
    yesterday = datetime.now(KST) - timedelta(days=1)
    start_dt = yesterday - timedelta(days=14)  # 7거래일 커버
    
    trends = fetch_investor_trend_daily(
        token, APP_KEY, APP_SECRET, URL_BASE,
        market_code="J",  # 코스피
        start_date=_yyyymmdd(start_dt),
        end_date=_yyyymmdd(yesterday),
        verbose=True
    )

    if not trends:
        print("❌ 데이터를 가져오지 못했습니다.")
        print("   - 실전투자 계정이 아니면 이 API를 사용할 수 없습니다.")
        print("   - 모의투자 계정은 '주식현재가 투자자' API만 지원합니다.")
        raise SystemExit(1)

    # 최근 7개만 출력
    last7 = trends[-7:]
    
    print("\n📈 최근 7거래일 코스피 투자자별 순매수 (일자 / 개인 / 외국인 / 기관)")
    print("-" * 90)
    
    # 요일 매핑
    weekday_kr = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"]
    
    for row in last7:
        ymd = row["date"]
        try:
            dt = datetime.strptime(ymd, "%Y%m%d")
            day_of_week = weekday_kr[dt.weekday()]
            date_with_dow = f"{ymd}{day_of_week}"
        except Exception:
            date_with_dow = ymd
        
        indiv = row["individual_amt"]
        foreign = row["foreign_amt"]
        inst = row["institution_amt"]
        
        # 금액 단위: 억원 (100,000,000원 = 1억)
        indiv_billion = indiv / 100_000_000
        foreign_billion = foreign / 100_000_000
        inst_billion = inst / 100_000_000
        
        print(f"{date_with_dow} | {indiv_billion:>10,.1f}억 | {foreign_billion:>10,.1f}억 | {inst_billion:>10,.1f}억")
    
    print("-" * 90)
    
    # 기간 합계
    total_indiv = sum(r["individual_amt"] for r in last7) / 100_000_000
    total_foreign = sum(r["foreign_amt"] for r in last7) / 100_000_000
    total_inst = sum(r["institution_amt"] for r in last7) / 100_000_000
    
    print(f"{'7일 합계':<12} | {total_indiv:>10,.1f}억 | {total_foreign:>10,.1f}억 | {total_inst:>10,.1f}억")
    print("\n💡 양수=순매수(매수>매도), 음수=순매도(매도>매수)")
