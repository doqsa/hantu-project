"""
remove_order.py: 한국투자증권 주문 관리 전용 모듈
- 미체결 주문 조회
- 주문 취소
- 주문 정정

사용 예:
    from remove_order import get_pending_orders, cancel_order, cancel_all_orders
    
    # 미체결 주문 조회
    orders = get_pending_orders(token, app_key, app_secret, cano, acnt_prdt_cd, url_base)
    
    # 특정 주문 취소
    cancel_order(token, app_key, app_secret, cano, acnt_prdt_cd, url_base, order_no, qty, price)
    
    # 모든 미체결 주문 취소
    cancel_all_orders(token, app_key, app_secret, cano, acnt_prdt_cd, url_base)
"""

import requests
import json
import time
from typing import Optional, List, Dict


def get_pending_orders(token: str, 
                      app_key: str, 
                      app_secret: str,
                      cano: str,
                      acnt_prdt_cd: str,
                      url_base: str) -> Optional[Dict]:
    """
    미체결 주문 내역 조회
    
    Args:
        token: 접근 토큰
        app_key: API 앱 키
        app_secret: API 앱 시크릿
        cano: 계좌번호
        acnt_prdt_cd: 계좌상품코드
        url_base: API 베이스 URL
        
    Returns:
        미체결 주문 정보 딕셔너리 또는 None
    """
    print("\n🔍 미체결 주문 조회를 시작합니다...")
    
    PATH = "/uapi/domestic-stock/v1/trading/inquire-psbl-rvsecncl"
    URL = url_base + PATH
    
    HEADERS = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "TTTC8036R"  # 미체결 조회 TR_ID
    }
    
    PARAMS = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
        "INQR_DVSN_1": "0",  # 조회구분1 (0:전체)
        "INQR_DVSN_2": "0"   # 조회구분2 (0:전체)
    }
    
    try:
        res = requests.get(URL, headers=HEADERS, params=PARAMS, timeout=10)
        response_data = res.json()
        
        print(f"📡 응답 상태: {res.status_code}")
        
        if res.status_code == 200 and response_data.get('rt_cd') == '0':
            print("✅ [미체결 주문 조회 성공]")
            print("=" * 60)
            
            if response_data.get('output') and len(response_data['output']) > 0:
                orders = response_data['output']
                print(f"📋 [미체결 주문] {len(orders)}건\n")
                
                for i, order in enumerate(orders, 1):
                    print(f"   {i}. {order.get('prdt_name', 'N/A')}")
                    print(f"      주문번호: {order.get('odno', 'N/A')}")
                    print(f"      주문구분: {order.get('sll_buy_dvsn_cd_name', 'N/A')}")
                    print(f"      주문가격: {int(order.get('ord_unpr', 0)):,}원")
                    print(f"      주문수량: {int(order.get('ord_qty', 0)):,}주")
                    print(f"      미체결수량: {int(order.get('rmn_qty', 0)):,}주")
                    print(f"      주문시각: {order.get('ord_tmd', 'N/A')}\n")
                
                print("=" * 60)
                return response_data
            else:
                print("📋 미체결 주문이 없습니다.")
                print("=" * 60)
                return None
        else:
            error_msg = response_data.get('msg1', 'API 오류')
            print(f"❌ [미체결 주문 조회 실패]: {error_msg}")
            return None
    
    except Exception as e:
        print(f"❌ [미체결 주문 조회 오류]: {e}")
        return None


def cancel_order(token: str,
                app_key: str,
                app_secret: str,
                cano: str,
                acnt_prdt_cd: str,
                url_base: str,
                order_no: str,
                order_qty: str,
                order_price: str) -> bool:
    """
    특정 미체결 주문 취소
    
    Args:
        token: 접근 토큰
        app_key: API 앱 키
        app_secret: API 앱 시크릿
        cano: 계좌번호
        acnt_prdt_cd: 계좌상품코드
        url_base: API 베이스 URL
        order_no: 원주문번호
        order_qty: 주문수량
        order_price: 주문가격
        
    Returns:
        성공 시 True, 실패 시 False
    """
    print(f"\n🔄 주문번호 {order_no} 취소를 시도합니다...")
    
    PATH = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
    URL = url_base + PATH
    
    HEADERS = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "TTTC0803U"  # 주문 취소 TR_ID
    }
    
    BODY = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "KRX_FWDG_ORD_ORGNO": "",  # 원주문조직번호
        "ORGN_ODNO": order_no,     # 원주문번호
        "ORD_DVSN": "00",          # 주문구분 (00:지정가)
        "RVSE_CNCL_DVSN_CD": "02", # 정정취소구분 (02:취소)
        "ORD_QTY": str(order_qty), # 주문수량
        "ORD_UNPR": str(order_price), # 주문단가
        "QTY_ALL_ORD_YN": "Y"      # 잔량전부주문여부
    }
    
    try:
        res = requests.post(URL, headers=HEADERS, data=json.dumps(BODY), timeout=10)
        response_data = res.json()
        
        print(f"📡 응답 상태: {res.status_code}")
        
        if res.status_code == 200 and response_data.get('rt_cd') == '0':
            print(f"✅ [주문 취소 성공] 주문번호: {order_no}")
            return True
        else:
            error_msg = response_data.get('msg1', 'API 오류')
            print(f"❌ [주문 취소 실패]: {error_msg}")
            return False
    
    except Exception as e:
        print(f"❌ [주문 취소 오류]: {e}")
        return False


def cancel_all_orders(token: str,
                     app_key: str,
                     app_secret: str,
                     cano: str,
                     acnt_prdt_cd: str,
                     url_base: str,
                     confirm: bool = True) -> int:
    """
    모든 미체결 주문 취소
    
    Args:
        token: 접근 토큰
        app_key: API 앱 키
        app_secret: API 앱 시크릿
        cano: 계좌번호
        acnt_prdt_cd: 계좌상품코드
        url_base: API 베이스 URL
        confirm: 사용자 확인 여부 (기본값: True)
        
    Returns:
        취소된 주문 수
    """
    # 미체결 주문 조회
    pending_orders = get_pending_orders(token, app_key, app_secret, cano, acnt_prdt_cd, url_base)
    
    if not pending_orders or not pending_orders.get('output'):
        print("\n취소할 미체결 주문이 없습니다.")
        return 0
    
    orders = pending_orders['output']
    
    # 사용자 확인
    if confirm:
        print(f"\n⚠️ {len(orders)}건의 미체결 주문을 모두 취소하시겠습니까? (y/n): ", end="")
        user_input = input().strip().lower()
        
        if user_input != 'y':
            print("⏭️ 주문 취소를 건너뜁니다.")
            return 0
    
    # 모든 주문 취소
    cancelled_count = 0
    for order in orders:
        order_no = order.get('odno')
        order_qty = order.get('rmn_qty')  # 미체결 수량
        order_price = order.get('ord_unpr')
        
        success = cancel_order(token, app_key, app_secret, cano, acnt_prdt_cd, 
                              url_base, order_no, order_qty, order_price)
        
        if success:
            cancelled_count += 1
        
        time.sleep(0.2)  # API 호출 간격
    
    print(f"\n✅ {cancelled_count}/{len(orders)}건의 주문이 취소되었습니다.")
    return cancelled_count


def display_order_summary(orders_data: Optional[Dict]) -> None:
    """
    미체결 주문 요약 정보 출력
    
    Args:
        orders_data: get_pending_orders 반환값
    """
    if not orders_data or not orders_data.get('output'):
        print("\n📋 미체결 주문이 없습니다.")
        return
    
    orders = orders_data['output']
    
    print(f"\n{'='*60}")
    print(f"📊 미체결 주문 요약 ({len(orders)}건)")
    print(f"{'='*60}")
    
    buy_orders = [o for o in orders if o.get('sll_buy_dvsn_cd') == '02']
    sell_orders = [o for o in orders if o.get('sll_buy_dvsn_cd') == '01']
    
    print(f"  매수 주문: {len(buy_orders)}건")
    print(f"  매도 주문: {len(sell_orders)}건")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    """
    주문 관리 전용 실행 파일
    미체결 주문 조회 및 취소 작업을 수행합니다.
    """
    from token_manage import get_token_for_api
    import key
    
    print("🚀 한국투자증권 주문 관리 프로그램")
    print(f"📁 토큰 파일: {key.TOKEN_FILE}")
    print(f"👤 계좌번호: 43407510-01")
    
    # 토큰 발급
    final_token = get_token_for_api(key.APP_KEY, key.APP_SECRET, key.URL_BASE)
    
    if not final_token:
        print("💥 토큰 발급 실패. 프로그램을 종료합니다.")
        exit(1)
    
    print(f"🔑 토큰 획득 성공: {final_token[:30]}...")
    
    # 미체결 주문 조회 및 취소
    CANO = "43407510"
    ACNT_PRDT_CD = "01"
    
    cancelled_count = cancel_all_orders(
        final_token,
        key.APP_KEY,
        key.APP_SECRET,
        CANO,
        ACNT_PRDT_CD,
        key.URL_BASE,
        confirm=True
    )
    
    print(f"\n🎉 주문 관리 작업이 완료되었습니다.")
    print(f"✅ {cancelled_count}건의 주문이 처리되었습니다.")
