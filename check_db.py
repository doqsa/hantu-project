import sqlite3
import pandas as pd

DB_FILE = "trading.db"

def check_data():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 테이블 목록 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"📂 현재 DB에 있는 테이블: {tables}")
    
    # realtime_log 테이블 데이터 확인
    try:
        # 가장 최근 데이터 5개만 가져오기
        query = "SELECT * FROM realtime_log ORDER BY timestamp DESC LIMIT 5"
        df = pd.read_sql(query, conn)
        
        print("\n📊 [최근 저장된 데이터 5건]")
        if not df.empty:
            print(df)
        else:
            print("데이터가 아직 없습니다. (장 운영 시간인지 확인하세요)")
            
    except Exception as e:
        print(f"테이블 조회 에러 (아직 데이터가 안 쌓였을 수 있음): {e}")
        
    conn.close()

if __name__ == "__main__":
    check_data()