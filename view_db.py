import sqlite3
import pandas as pd

# DB 연결
conn = sqlite3.connect("trading.db")

# 저장된 데이터 불러오기 (최근 5개만)
df = pd.read_sql("SELECT * FROM price_log ORDER BY timestamp DESC LIMIT 5", conn)

print("\n📊 [최근 수집된 데이터 5건]")
print(df)

conn.close()