import requests
import json
import time
import sqlite3
import datetime
from token_manage import get_token_for_api
import key  # key.py에서 설정 가져오기

# =========================================================
# --- 설정 ---
# =========================================================
STOCK_CODE = "069500"  # KODEX 200 종목코드
DB_FILE = "trading.db" # 데이터베이스 파일 이름

# =========================================================
# --- 1. 데이터베이스 준비 (SQLite) ---
# =========================================================
def init_db():
    """DB 테이블이 없으면 생성"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 시간(timestamp), 종목코드(code), 현재가(close), 거래량(volume) 저장
    query = """
    CREATE TABLE IF NOT EXISTS price_log (
        timestamp TEXT PRIMARY KEY,
        code TEXT,
        price INTEGER,
        volume INTEGER
    )
    """
    cursor.execute(query)
    conn.commit()
    conn.close()
    print(f"📁 [DB] {DB_FILE} 준비 완료.")

def save_to_db(code, price, volume):
    """DB에 가격 정보 저장"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    query = "INSERT OR REPLACE INTO price_log (timestamp, code, price, volume) VALUES (?, ?, ?, ?)"
    cursor.execute(query, (now, code, price, volume))
    
    conn.commit()
    conn.close()
    print(f"💾 [저장] {now} | {code} | {price}원 | {volume}주")

# =========================================================
# --- 2. 한국투자증권 API: 주식 현재가 조회 ---
# =========================================================
def get_current_price(token):
    """KODEX 200 현재가 조회"""
    URL = f"{key.URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-price"
    
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": key.APP_KEY,
        "appsecret": key.APP_SECRET,
        "tr_id": "FHKST01010100"  # 주식 현재가 시세 TR ID
    }
    
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",  # 시장 구분 (J: 주식/ETF)
        "FID_INPUT_ISCD": STOCK_CODE    # 종목 코드 (069500)
    }
    
    try:
        res = requests.get(URL, headers=headers, params=params)
        data = res.json()
        
        if res.status_code == 200 and data['rt_cd'] == '0':
            # output 딕셔너리에서 필요한 정보 추출
            # stck_prpr: 현재가, acml_vol: 누적 거래량
            price = int(data['output']['stck_prpr'])
            volume = int(data['output']['acml_vol'])
            return price, volume
        else:
            print(f"❌ API 오류: {data['msg1']}")
            return None, None
            
    except Exception as e:
        print(f"💥 통신 오류: {e}")
        return None, None

# =========================================================
# --- 3. 메인 실행 (무한 루프) ---
# =========================================================
if __name__ == "__main__":
    print(f"🚀 [KODEX 200] 데이터 수집기를 가동합니다...")
    init_db() # DB 초기화
    
    while True:
        try:
            # 1. 현재 시간 확인
            now = datetime.datetime.now()
            
            # 2. 장 운영 시간 체크 (09:00 ~ 15:30)
            # (테스트를 위해 주석 처리하거나 시간을 조정해서 쓰세요. 지금은 24시간 돌아가게 둡니다)
            # if not (9 <= now.hour < 16):
            #     print("💤 장 마감 시간입니다. (대기 중)")
            #     time.sleep(60) 
            #     continue

            # 3. 토큰 발급
            token = get_token_for_api(key.APP_KEY, key.APP_SECRET, key.URL_BASE)
            
            # 4. 가격 조회 및 저장
            if token:
                price, volume = get_current_price(token)
                if price is not None:
                    save_to_db(STOCK_CODE, price, volume)
            
            # 5. 1분(60초) 대기
            time.sleep(60)

        except KeyboardInterrupt:
            print("\n🛑 프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"⚠️ 에러 발생: {e}")
            time.sleep(10)