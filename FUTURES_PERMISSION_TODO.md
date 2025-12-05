# 선물 거래 권한 신청 체크리스트

## 현재 상태
- ✅ 선물 코드 자동 조회 모듈: `fetch_futures_code.py` (활성화)
- ✅ 코스피200 선물 코드: `101S9000` (근월물) 자동 감지
- ✅ KODEX 200 체결 데이터: 정상 작동 (1,000+ 레코드)
- ⏸️ KODEX 200 호가 데이터: "invalid tr_key" 에러 (권한 확인 필요)
- ⏸️ KOSPI200 선물 데이터: "invalid tr_key" 에러 (권한 신청 필요)

## 필요 사항

### 1. 선물 거래 권한
- **선물 거래 교육 이수** (한국투자증권)
  - 온라인 교육 완료
  - 교육 이수 증명서 획득
  - 권한 신청

### 2. 호가 데이터 권한
- 현재 상태: `H0STNHG0` 구독 시 "invalid tr_key" 에러
- 가능한 원인:
  - 호가 실시간 데이터 구독 권한 미보유
  - ETF 호가 제공 제한 (선택적 제공 상품)
  - 계정 레벨 제한
- **권장사항**: 증권사에 문의하여 호가 데이터 권한 확인

## 호가 데이터 저장 문제 진단 완료 ✅

### ✅ 검증된 사항:
1. **DB 테이블 구조**: 정상 ✓
   ```
   kodex200_hoga 테이블: 50개 컬럼 정확히 매칭
   - id (auto_increment)
   - bsop_date, hoga_time
   - imbalance_ratio, wap_ask, wap_bid, resistance_wall, support_wall
   - ask_price_1~10, ask_vol_1~10 (20개)
   - bid_price_1~10, bid_vol_1~10 (20개)
   - total_ask_qty, total_bid_qty
   - created_at
   ```
   
2. **SQL INSERT 테스트**: 성공 ✓
   - test_hoga_insert.py: 테스트 데이터 삽입 성공
   - 컬럼 개수, 데이터 타입 모두 정상

3. **코드 구현**: 정상 ✓
   - `kodex200_data.py`: H0STNHG0 파싱 완료
   - `websocket_handler.py`: H0STNHG0 필드 매핑 완료
   - `db_handler.py`: _insert_hoga() 함수 정상
   
4. **WebSocket 메시지 수신**: 도착함 ✓
   - 로그 확인: `[WS] 📨 메시지 수신: TR_ID=H0STNHG0`

### ❌ 실제 문제 원인:
```
[WS] 🔑 H0STNHG0 권한 거부: JSON PARSING ERROR : invalid tr_key
```

**분석:**
- KIS 서버가 호가 구독 요청을 거부함 (rt_cd=9, msg_cd=OPSP8993)
- 메시지에 `output` 필드가 없으므로 데이터 파싱 불가
- 결과: DB에 저장될 데이터 없음

**가능한 원인:**
1. 계정에 호가 실시간 구독 권한 없음
2. KODEX 200 ETF는 호가 데이터 미제공 상품
3. 계정 레벨이 기본 레벨 (프리미엄/VIP 레벨 필요 가능)

### 📞 해결 방법:
한국투자증권 고객센터 문의:
1. "호가(orderbook) 실시간 데이터 구독 권한 여부 확인"
2. "KODEX 200 ETF 호가 데이터 제공 여부 확인"
3. 필요시 권한 신청 또는 계정 업그레이드

📁 파일: `core/websocket_handler.py` (라인 ~200)

현재 (비활성):
```python
# 2. KODEX 200 호가 (H0STNHG0) - [주석 처리] invalid tr_key 에러 (권한 확인 필요)
# await websocket.send(self._create_subscription_payload("H0STNHG0", KODEX_200_CODE))
# print(f"[WS] 호가 구독 요청 시도 (H0STNHG0)")
```

권한 확인 후 활성화할 코드:
```python
# 2. KODEX 200 호가 (H0STNHG0)
await websocket.send(self._create_subscription_payload("H0STNHG0", KODEX_200_CODE))
print(f"[WS] 호가 구독 요청 시도 (H0STNHG0)")
```

또한 H0STNHG0 필드 매핑도 확인했습니다 (websocket_handler.py 라인 ~145):
```python
elif tr_id == "H0STNHG0":
    data_list = [
        str(output.get("stck_hour", "")),            # 호가시간
        str(output.get("stck_prpr", "")),            # 현재가
        str(output.get("askp1", "")),                # 매도호가1
        str(output.get("bidp1", "")),                # 매수호가1
        str(output.get("askp_rsqn1", "")),           # 매도수량1
        str(output.get("bidp_rsqn1", "")),           # 매수수량1
    ]
```

### 1단계: WebSocket 구독 활성화
📁 파일: `core/websocket_handler.py` (라인 ~200)

현재 (비활성):
```python
# 3. 선물 체결가 (H0FCCNT0) - [주석 처리] 선물 거래 권한 신청 필요
# if self.futures_code:
#     await websocket.send(self._create_subscription_payload("H0FCCNT0", self.futures_code))
#     print(f"[WS] 선물({self.futures_code}) 구독 요청 완료")
if self.futures_code:
    print(f"[WS] 선물 구독 비활성화 중 (권한 신청 필요): {self.futures_code}")
```

활성화할 코드:
```python
# 3. 선물 체결가 (H0FCCNT0)
if self.futures_code:
    await websocket.send(self._create_subscription_payload("H0FCCNT0", self.futures_code))
    print(f"[WS] 선물({self.futures_code}) 구독 요청 완료")
```

### 2단계: 선물 데이터 처리 활성화
📁 파일: `data/futures_data.py` (라인 ~108)

현재 (비활성):
```python
async def run(self):
    print("[FuturesData] [대기중] 선물 거래 권한 신청 후 활성화 예정...")
    try:
        await asyncio.sleep(float('inf'))
    except asyncio.CancelledError:
        print("[FuturesData] 정상 종료됨")
        raise
```

활성화할 코드:
```python
async def run(self):
    print("[FuturesData] 데이터 처리 루프 시작...")
    try:
        while True:
            raw_msg = await self.raw_queue.get()
            data = self._parse_data(raw_msg)
            
            if data:
                print(f"[FuturesData] 🚀 선물 데이터 파싱 성공: {data.get('현재가')}")
                await self.strategy_queue.put(data)
                
                if self.db_queue:
                    db_packet = {
                        "table": "kospi200_futures",
                        "data": data
                    }
                    await self.db_queue.put(db_packet)
                    print(f"[FuturesData] 📝 DB 큐로 전송됨")
    except asyncio.CancelledError:
        print("[FuturesData] 정상 종료됨")
        raise
```

## 참고
- `fetch_futures_code.py`: 선물 코드 조회 모듈 (항상 활성)
- 코드 조회는 이미 자동화되어 있음
- 데이터 수집만 권한 신청 후 활성화 필요
