import requests
import json
import time
import sqlite3
import datetime
from token_manage import get_token_for_api
import key

# =========================================================
# --- 설정 ---
# =========================================================
STOCK_CODE = "069500"  # KODEX 200
DB_FILE = "trading.db"

# =========================================================
# --- 1. DB 준비 (호가 정보 컬럼 추가) ---
# =========================================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # total_ask: 총 매도 잔량, total_bid: 총 매수 잔량
    query = """
    CREATE TABLE IF NOT EXISTS price_log (
        timestamp TEXT PRIMARY KEY,
        code TEXT,
        price INTEGER,
        volume INTEGER,
        total_ask_qty INTEGER, 
        total_bid_qty INTEGER
    )
    """
    cursor.execute(query)
    
    # 기존에 테이블이 있는데 컬럼이 없을 경우를 대비한 안전장치 (건너뛰어도 됨)
    try:
        cursor.execute("ALTER TABLE price_log ADD COLUMN total_ask_qty INTEGER")
        cursor.execute("ALTER TABLE price_log ADD COLUMN total_bid_qty INTEGER")
    except:
        pass # 이미 컬럼이 있으면 무시

    conn.commit()
    conn.close()
    print(f"📁 [DB] {DB_FILE} (호가 포함) 준비 완료.")

def save_to_db(code, price, volume, ask_qty, bid_qty):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    query = """
    INSERT OR REPLACE INTO price_log 
    (timestamp, code, price, volume, total_ask_qty, total_bid_qty) 
    VALUES (?, ?, ?, ?, ?, ?)
    """
    cursor.execute(query, (now, code, price, volume, ask_qty, bid_qty))
    conn.commit()
    conn.close()
    
    # 체결강도 비슷하게 계산 (매수잔량이 많으면 빨간색, 매도잔량이 많으면 파란색 느낌)
    power_str = "매수우위🔥" if bid_qty > ask_qty else "매도우위💧"
    print(f"💾 {now} | {price}원 | {power_str} (매수잔량:{bid_qty} vs 매도잔량:{ask_qty})")

# =========================================================
# --- 2. 호가(Asking Price) 조회 API ---
# =========================================================
def get_hoga_data(token):
    # 호가 조회 URL (주식현재가 호가 예상체결)
    URL = f"{key.URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
    
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": key.APP_KEY,
        "appsecret": key.APP_SECRET,
        "tr_id": "FHKST01010200"  # 주식 호가 조회용 TR ID
    }
    
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": STOCK_CODE
    }
    
    try:
        res = requests.get(URL, headers=headers, params=params)
        data = res.json()
        
        if res.status_code == 200 and data['rt_cd'] == '0':
            out2 = data['output2'] # 호가 잔량 정보는 output2에 있음
            
            # aspr_acml_vol: 총 매도 호가 잔량
            # bid_acml_vol: 총 매수 호가 잔량
            # stck_prpr: 현재가 (호가 조회시 현재가도 같이 줌)
            
            total_ask = int(out2['aspr_acml_vol'])
            total_bid = int(out2['bid_acml_vol'])
            current_price = int(out2['stck_prpr'])
            # 거래량은 output1에서 가져오거나 해야 하는데, 여기서는 output2의 호가 정보 위주로 씀
            # output1이 비어있을 수 있으므로 안전하게 처리
            
            return current_price, 0, total_ask, total_bid
        else:
            print(f"❌ API 오류: {data.get('msg1')}")
            return None, None, None, None
            
    except Exception as e:
        print(f"💥 통신 오류: {e}")
        return None, None, None, None

# =========================================================
# --- 3. 실행 ---
# =========================================================
if __name__ == "__main__":
    print(f"🚀 [KODEX 200] 호가 데이터 수집기 시작")
    init_db()
    
    while True:
        try:
            token = get_token_for_api(key.APP_KEY, key.APP_SECRET, key.URL_BASE)
            if token:
                price, vol, ask, bid = get_hoga_data(token)
                if price is not None:
                    save_to_db(STOCK_CODE, price, vol, ask, bid)
            
            time.sleep(60) # 1분 간격

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"에러: {e}")
            time.sleep(10)