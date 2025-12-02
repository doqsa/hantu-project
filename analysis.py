import sqlite3
import pandas as pd

# 1. DB에서 데이터 꺼내오기
conn = sqlite3.connect("trading.db")
query = "SELECT * FROM price_log ORDER BY timestamp ASC"
df = pd.read_sql(query, conn)
conn.close()

# 데이터가 너무 적으면 분석 불가 (최소 15개 필요)
if len(df) < 15:
    print("⚠️ 분석을 위한 데이터가 부족합니다. (수집기를 좀 더 돌려주세요)")
    exit()

# 2. RSI (상대강도지수) 계산하기 - 매수 타이밍 잡는 핵심 지표
def calculate_rsi(data, period=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

df['RSI'] = calculate_rsi(df['price'])

# 3. 호가 잔량 비율 계산 - 힘의 균형
# (매수잔량이 많으면 > 1, 매도잔량이 많으면 < 1)
df['Power'] = df['total_bid_qty'] / df['total_ask_qty']

# 4. 분석 결과 출력 (가장 최근 1개)
latest = df.iloc[-1]
rsi = latest['RSI']
power = latest['Power']

print("\n📊 [현재 시장 분석 결과]")
print(f"시간: {latest['timestamp']}")
print(f"현재가: {latest['price']} 원")
print("-" * 30)

#전략 1: RSI 판단
if rsi < 30:
    print(f"🔵 RSI: {rsi:.1f} → [과매도 구간] 줍줍 찬스! (적극 매수 고려)")
elif rsi > 70:
    print(f"🔴 RSI: {rsi:.1f} → [과매수 구간] 너무 올랐음 (매도 고려)")
else:
    print(f"⚪ RSI: {rsi:.1f} → [중립 구간] 관망")

#전략 2: 호가 힘 판단
if power > 1.5:
    print(f"🔥 호가: 매수세가 {power:.1f}배 강함 (상승 압력)")
elif power < 0.7:
    print(f"💧 호가: 매도세가 더 강함 (하락 압력)")
else:
    print(f"⚖️ 호가: 팽팽한 균형 상태")