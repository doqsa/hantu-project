"""
dow.py: 코스피(KOSPI) 지수 기간별 시세를 조회하여 다우이론 분석
- TR ID: FHKUP03500100 (업종 기간별 시세 - 일/주/월/년)
- Endpoint: /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice
"""

import argparse
import requests
from datetime import datetime, timedelta
from b_account import APP_KEY, APP_SECRET, URL_BASE
from token_manage import get_token_for_api


def fetch_kospi_period_price(token: str, start_date: str, end_date: str, period_code: str = "D", verbose: bool = True):
    """코스피 지수 기간별 시세를 조회한다.
    
    Args:
        token: 인증 토큰
        start_date: 조회 시작일 (YYYYMMDD)
        end_date: 조회 종료일 (YYYYMMDD)
        period_code: 기간 구분 코드 (D:일, W:주, M:월, Y:년)
        verbose: 상세 로그 출력 여부
    
    Returns:
        list or None: 시세 데이터 리스트 (최신순), 실패 시 None
    """
    url = URL_BASE + "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
    
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKUP03500100",
    }
    
    params = {
        "FID_COND_MRKT_DIV_CODE": "U",  # U: 업종
        "FID_INPUT_ISCD": "0001",        # 0001: KOSPI 지수
        "FID_INPUT_DATE_1": start_date,  # 조회 시작일
        "FID_INPUT_DATE_2": end_date,    # 조회 종료일
        "FID_PERIOD_DIV_CODE": period_code,  # D:일, W:주, M:월, Y:년
    }
    
    if verbose:
        print(f"\n📡 [KOSPI 기간별 시세 조회]")
        print(f"   기간: {start_date} ~ {end_date}")
        print(f"   구분: {period_code} (D:일, W:주, M:월, Y:년)")
    
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        
        if verbose:
            print(f"   응답 코드: {res.status_code}")
        
        if res.status_code != 200:
            if verbose:
                print(f"❌ HTTP 오류: {res.text[:300]}")
            return None
        
        data = res.json()
        
        if data.get("rt_cd") == "0":
            output = data.get("output2") or data.get("output") or []
            
            if verbose:
                print(f"✅ 조회 성공: {len(output)}개 데이터")
            
            # 데이터 파싱
            result = []
            for item in output:
                result.append({
                    "date": item.get("stck_bsop_date"),  # 영업일자
                    "close": float(item.get("bstp_nmix_prpr", 0)),  # 업종지수현재가
                    "open": float(item.get("bstp_nmix_oprc", 0)),   # 업종지수시가
                    "high": float(item.get("bstp_nmix_hgpr", 0)),   # 업종지수최고가
                    "low": float(item.get("bstp_nmix_lwpr", 0)),    # 업종지수최저가
                    "volume": int(item.get("acml_vol", 0)),         # 누적거래량
                })
            
            return result
        else:
            if verbose:
                print(f"❌ API 오류: {data.get('msg1', '알 수 없음')} (코드: {data.get('rt_cd')})")
            return None
            
    except Exception as e:
        if verbose:
            print(f"❌ 예외 발생: {e}")
        return None


def analyze_dow_theory(price_data):
    """다우이론에 따라 추세를 분석한다.
    
    Args:
        price_data: 시세 데이터 리스트 (최신순)
    
    Returns:
        dict: 분석 결과 (추세, 국면 등)
    """
    if not price_data or len(price_data) < 5:
        return {"error": "분석에 필요한 데이터가 부족합니다 (최소 5일 필요)"}
    
    # 날짜 오름차순으로 정렬 (과거 -> 현재)
    data = sorted(price_data, key=lambda x: x['date'])
    
    # 고점과 저점 찾기
    highs = [d['high'] for d in data]
    lows = [d['low'] for d in data]
    
    # 최근 추세 판단 (마지막 3개 데이터 기준)
    recent_highs = highs[-3:]
    recent_lows = lows[-3:]
    
    # 고점이 높아지고 저점도 높아지면 상승 추세
    if recent_highs[-1] > recent_highs[0] and recent_lows[-1] > recent_lows[0]:
        trend = "상승 추세 (Uptrend)"
        phase = "축적기 또는 상승기"
    # 고점이 낮아지고 저점도 낮아지면 하락 추세
    elif recent_highs[-1] < recent_highs[0] and recent_lows[-1] < recent_lows[0]:
        trend = "하락 추세 (Downtrend)"
        phase = "분산기 또는 공황기"
    else:
        trend = "횡보 (Sideways)"
        phase = "전환기 또는 불명확"
    
    return {
        "trend": trend,
        "phase": phase,
        "latest_close": data[-1]['close'],
        "latest_date": data[-1]['date'],
        "period_high": max(highs),
        "period_low": min(lows),
        "data_count": len(data),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KOSPI 지수 기간별 시세 조회 및 다우이론 분석")
    parser.add_argument("--days", type=int, default=30, help="조회할 기간 (일수, 기본값: 30)")
    parser.add_argument("--period", choices=["D", "W", "M", "Y"], default="D", help="기간 구분 (D:일, W:주, M:월, Y:년)")
    parser.add_argument("--quiet", action="store_true", help="상세 로그 숨김")
    args = parser.parse_args()

    print("[KOSPI 다우이론 분석]")
    
    # 토큰 획득
    token = get_token_for_api(APP_KEY, APP_SECRET, URL_BASE)
    if not token:
        print("❌ 토큰 획득 실패")
        exit(1)
    
    # 조회 기간 계산
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)
    
    # 기간별 시세 조회
    price_data = fetch_kospi_period_price(
        token,
        start_date.strftime("%Y%m%d"),
        end_date.strftime("%Y%m%d"),
        args.period,
        verbose=not args.quiet
    )
    
    if not price_data:
        print("\n❌ 시세 조회 실패")
        exit(1)
    
    # 최근 5개 데이터 출력
    print(f"\n📊 [최근 {min(5, len(price_data))}일 시세]")
    for i, data in enumerate(price_data[:5]):
        print(f"   {i+1}. {data['date']}: 종가 {data['close']:,.2f} (고가: {data['high']:,.2f}, 저가: {data['low']:,.2f})")
    
    # 다우이론 분석
    analysis = analyze_dow_theory(price_data)
    
    print("\n🔍 [다우이론 분석 결과]")
    if "error" in analysis:
        print(f"   {analysis['error']}")
    else:
        print(f"   추세: {analysis['trend']}")
        print(f"   국면: {analysis['phase']}")
        print(f"   최근 종가: {analysis['latest_close']:,.2f} ({analysis['latest_date']})")
        print(f"   기간 최고: {analysis['period_high']:,.2f}")
        print(f"   기간 최저: {analysis['period_low']:,.2f}")
        print(f"   분석 데이터: {analysis['data_count']}일")
