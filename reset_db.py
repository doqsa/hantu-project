import os
import sqlite3

DB_FILE = "trading.db"

def reset_database():
    print("=" * 40)
    print(f"🚨 경고: {DB_FILE} 데이터베이스를 초기화합니다.")
    print("모든 거래 기록과 수집된 데이터가 영구적으로 삭제됩니다.")
    print("=" * 40)
    
    # 1. 안전장치: 정말 지울 건지 물어봄
    confirm = input("정말로 초기화 하시겠습니까? (yes 입력): ")
    
    if confirm.lower() != 'yes':
        print("❌ 취소되었습니다. 데이터가 안전하게 유지됩니다.")
        return

    # 2. 기존 파일 삭제 (가장 확실한 방법)
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
            print(f"\n🗑️ 기존 {DB_FILE} 파일을 삭제했습니다.")
        except Exception as e:
            print(f"⚠️ 파일 삭제 중 오류 발생 (사용 중일 수 있음): {e}")
            return
    else:
        print(f"\nℹ️ {DB_FILE} 파일이 이미 없습니다.")

    # 3. 새로운 빈 테이블 생성 (호가 컬럼 포함)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 최신 스펙(호가 포함)으로 테이블 생성
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
    conn.commit()
    conn.close()
    
    print(f"✅ {DB_FILE} 초기화 및 재생성 완료! (준비 끝)")

if __name__ == "__main__":
    reset_database()