import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

conn = pymysql.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    charset='utf8mb4'
)

cursor = conn.cursor()

print("=" * 60)
print("kodex200_trade 테이블 구조:")
print("=" * 60)
cursor.execute("DESCRIBE kodex200_trade")
for row in cursor.fetchall():
    print(f"  {row[0]:20s} {row[1]:15s}")

print("\n" + "=" * 60)
print("kodex200_hoga 테이블 구조: (첫 10개만)")
print("=" * 60)
cursor.execute("DESCRIBE kodex200_hoga")
rows = cursor.fetchall()
for row in rows[:10]:
    print(f"  {row[0]:20s} {row[1]:15s}")
print(f"  ... (총 {len(rows)}개 컬럼)")

print("\n" + "=" * 60)
print("kospi200_futures 테이블 구조:")
print("=" * 60)
cursor.execute("DESCRIBE kospi200_futures")
for row in cursor.fetchall():
    print(f"  {row[0]:20s} {row[1]:15s}")

cursor.close()
conn.close()
