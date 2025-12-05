# 환율 데이터 수집 활성화 패치

## 현재 상태
- ✅ `exchange_fetcher.py`: 60초마다 yfinance로 USD/KRW 환율 수집 중
- ✅ `market_exchange` 테이블: 존재함
- ❌ **DB 저장 로직 누락**: `db_handler.py`에 환율 처리 코드 없음

## 필요한 수정

### 1. `core/db_handler.py` 파일 수정

**184번 줄 근처 (`_insert_nav` 함수 다음)에 추가:**

```python
    async def _insert_exchange(self, conn, data):
        """환율 데이터 저장 (USD/KRW)"""
        sql = """
            INSERT INTO market_exchange (
                bsop_date, check_time, currency, rate, created_at
            ) VALUES (%s, %s, %s, %s, %s)
        """
        timestamp = data.get('timestamp')
        now_date = timestamp[:10].replace('-', '')
        now_time = timestamp[11:19].replace(':', '')
        
        args = (
            now_date, now_time,
            data.get('currency', 'USD'),
            data.get('rate'),
            timestamp
        )
        
        async with conn.cursor() as cur:
            await cur.execute(sql, args)
```

### 2. `core/db_handler.py` - `run()` 메서드 수정

**216번 줄 근처 (테이블 분기 처리 부분):**

기존:
```python
                        elif table_name == 'kodex200_nav': 
                            await self._insert_nav(conn, data)
                        else:
                            pass # 알 수 없는 테이블
```

변경:
```python
                        elif table_name == 'kodex200_nav': 
                            await self._insert_nav(conn, data)
                        elif data.get('type') == 'EXCHANGE':
                            await self._insert_exchange(conn, data)
                        elif data.get('type') == 'GLOBAL_MARKET':
                            pass  # 글로벌 시장 데이터 처리 (향후 구현)
                        else:
                            pass # 알 수 없는 테이블
```

## 수정 후 테스트 명령

```powershell
# 1분간 실행 후 환율 데이터 확인
$proc = Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "-u main.py" -PassThru -NoNewWindow
Start-Sleep -Seconds 70
$proc | Stop-Process -Force 2>$null

.\venv\Scripts\python.exe -c "import pymysql; conn = pymysql.connect(host='localhost', user='root', password='root', database='stock_db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM market_exchange'); cnt = cursor.fetchone()[0]; print(f'총 환율 레코드: {cnt}건'); cursor.execute('SELECT * FROM market_exchange ORDER BY created_at DESC LIMIT 3'); rows = cursor.fetchall(); [print(f'{i+1}. {r[1]} {r[2]} | {r[3]}: {r[4]}원') for i, r in enumerate(rows)]; conn.close()"
```

## 예상 결과
```
총 환율 레코드: 1건
1. 20251205 133545 | USD: 1425.50원
```
