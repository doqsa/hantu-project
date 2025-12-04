from datetime import datetime, time
import pytz # pip install pytz

class MarketTimeManager:
    def __init__(self):
        # 타임존 정의 (서머타임 자동 반영을 위해 pytz 사용 필수)
        self.kst_tz = pytz.timezone('Asia/Seoul')
        self.us_tz = pytz.timezone('America/New_York')

        # 1. 한국 주식 시장 (KOSPI/KODEX 200)
        # 정규장: 09:00 ~ 15:30
        self.kr_start = time(9, 0, 0)
        self.kr_end = time(15, 30, 0)

        # 2. 미국 주식 시장 (NYSE/NASDAQ) - 현지 시간 기준
        # 정규장: 09:30 ~ 16:00
        self.us_stock_start = time(9, 30, 0)
        self.us_stock_end = time(16, 0, 0)

        # 3. 미국 선물 시장 (CME Globex) - 현지 시간 기준
        # 일~금: 오후 6:00 ~ 익일 오후 5:00 (1시간 휴장: 17:00~18:00)
        self.us_futures_start = time(18, 0, 0) # 전일 18:00 시작
        self.us_futures_end = time(17, 0, 0)   # 당일 17:00 종료 (이후 1시간 휴장)

    def get_kst_time(self):
        """현재 한국 시간 반환"""
        return datetime.now(self.kst_tz)

    def is_kr_market_open(self):
        """
        한국 주식 정규장 열림 여부 (주말 제외)
        * 주의: 공휴일(설날, 추석 등)은 별도 라이브러리나 리스트로 처리 필요
        """
        now_kst = self.get_kst_time()
        
        # 주말 체크 (0:월 ~ 4:금, 5:토, 6:일)
        if now_kst.weekday() >= 5:
            return False

        now_time = now_kst.time()
        return self.kr_start <= now_time <= self.kr_end

    def is_us_stock_open(self):
        """미국 주식 정규장(본장) 열림 여부 (서머타임 자동 적용)"""
        # 현재 시간을 미국 시간으로 변환
        now_us = datetime.now(self.us_tz)

        if now_us.weekday() >= 5: # 주말 체크
            return False
            
        now_time = now_us.time()
        return self.us_stock_start <= now_time <= self.us_stock_end

    def is_us_futures_open(self):
        """
        미국 선물(CME) 시장 열림 여부
        - 운영: 일요일 18:00 ~ 금요일 17:00 (US ET 기준)
        - 휴장: 매일 17:00 ~ 18:00 (1시간 Maintenance)
        """
        now_us = datetime.now(self.us_tz)
        weekday = now_us.weekday() # 0:월 ~ 6:일
        now_time = now_us.time()

        # 1. 토요일(5)은 전체 휴장
        # (금요일 17:00에 닫혀서 일요일 18:00에 열림)
        if weekday == 5:
            return False

        # 2. 평일 (월~목) 브레이크 타임 (17:00 ~ 18:00) 체크
        # 이 시간에는 데이터 수신이 멈추거나 튀므로 매매 금지
        if 0 <= weekday <= 4:
            if time(17, 0, 0) <= now_time < time(18, 0, 0):
                return False

        # 3. 금요일 마감 (17:00 이후 휴장)
        if weekday == 4 and now_time >= time(17, 0, 0):
            return False

        # 4. 일요일 개장 전 (18:00 이전 휴장)
        if weekday == 6 and now_time < time(18, 0, 0):
            return False

        return True

# --- 테스트 코드 ---
if __name__ == "__main__":
    try:
        mm = MarketTimeManager()
        
        print(f"현재 한국 시간: {mm.get_kst_time().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"현재 미국 시간: {datetime.now(mm.us_tz).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        print("-" * 30)
        print(f"🇰🇷 한국 주식장 열림 : {mm.is_kr_market_open()}")
        print(f"🇺🇸 미국 주식장 열림 : {mm.is_us_stock_open()}")
        print(f"🌏 미국 선물장 열림 : {mm.is_us_futures_open()}")
        print("-" * 30)
        
    except Exception as e:
        print(f"[오류] {e}")
        print("터미널에서 'pip install pytz'를 실행했는지 확인해주세요.")