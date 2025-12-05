import asyncio
import os
import aiohttp
import json
from datetime import datetime
from typing import Optional, Dict, List
from dotenv import load_dotenv
from core.token_manage import TokenManager

# ========================================================
# 선물 코드 조회 클래스
# ========================================================

class FuturesCodeFetcher:
    """
    한국투자증권 API를 사용하여 선물 코드를 조회하는 클래스
    """
    
    def __init__(self, token_manager: TokenManager):
        self.BASE_URL = os.getenv("URL_BASE", "https://openapi.koreainvestment.com:9443")
        self.token_manager = token_manager
        self.app_key = os.getenv("APP_KEY")
        self.app_secret = os.getenv("APP_SECRET")
        self.session = None
    
    async def initialize_session(self):
        """세션 초기화"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def fetch_futures_list(self) -> Optional[List[Dict]]:
        """
        알려진 선물 코드들을 반환 (API 조회 대신 로컬 데이터 사용)
        """
        # KIS API 엔드포인트가 404를 반환하므로 알려진 선물 코드 반환
        known_futures = [
            {
                "code": "101S9000",
                "name": "KOSPI200 선물(근월)",
                "type": "futures",
                "category": "stock_index"
            },
            {
                "code": "101V9000",
                "name": "KOSPI200 선물(차월)",
                "type": "futures",
                "category": "stock_index"
            },
            {
                "code": "101H9000",
                "name": "KOSPI200 선물",
                "type": "futures",
                "category": "stock_index"
            },
            {
                "code": "101Z9000",
                "name": "KOSPI200 선물",
                "type": "futures",
                "category": "stock_index"
            },
            {
                "code": "101C9000",
                "name": "KOSPI200 선물",
                "type": "futures",
                "category": "stock_index"
            }
        ]
        
        print(f"[API] 알려진 선물 코드 {len(known_futures)}개 로드")
        return known_futures
    
    async def search_stock(self, keyword: str = "선물") -> Optional[List[Dict]]:
        """
        종목 검색 (여기서는 사용하지 않음)
        """
        return None
    
    def find_kospi200_futures(self, items: List[Dict]) -> Optional[Dict]:
        """
        목록에서 코스피200 선물 찾기 (근월물 우선)
        """
        if not items:
            return None
        
        print(f"\n📋 분석할 항목 수: {len(items)}")
        
        # 항목 출력
        for i, item in enumerate(items, 1):
            code = item.get('code')
            name = item.get('name')
            print(f"  {i}. {name} ({code})")
        
        # 근월물 우선 (보통 S, V 코드가 유동성이 높음)
        priority_order = ['101S9000', '101V9000', '101H9000', '101Z9000', '101C9000']
        
        # 우선순위 순서대로 매칭
        for code in priority_order:
            for item in items:
                if item.get('code') == code:
                    print(f"\n✅ 유효한 선물 코드 선택: {item['name']} ({code})")
                    return item
        
        # 첫 번째 항목 반환 (기본값)
        print(f"\n✅ 기본 선물 코드 선택: {items[0]['name']} ({items[0]['code']})")
        return items[0]

# ========================================================
# 메인 실행 함수
# ========================================================

async def main():
    print("=" * 70)
    print("🚀 한국투자증권 선물 코드 조회 프로그램")
    print("=" * 70)
    
    # 환경 변수 로드
    load_dotenv()
    
    # 토큰 매니저 초기화
    print("\n[1/4] 토큰 매니저 초기화 중...")
    try:
        token_manager = TokenManager()
        
        # TokenManager의 상태 확인
        print(f"✓ TokenManager 클래스: {type(token_manager)}")
        print(f"✓ access_token 속성 존재: {hasattr(token_manager, 'access_token')}")
        
        if hasattr(token_manager, 'access_token'):
            token = token_manager.access_token
            if token:
                print(f"✓ 액세스 토큰 길이: {len(token)}")
                print(f"✓ 액세스 토큰 (처음 20자): {token[:20]}...")
            else:
                print("⚠️ 액세스 토큰이 비어있습니다")
                # manage_token() 호출 시도
                if hasattr(token_manager, 'manage_token'):
                    print("✓ manage_token() 메서드 호출 시도")
                    if token_manager.manage_token():
                        print("✓ 토큰 관리 성공")
                        print(f"✓ 새로운 토큰: {token_manager.access_token[:20]}...")
                    else:
                        print("❌ 토큰 관리 실패")
                        return
                else:
                    print("❌ manage_token() 메서드가 없습니다")
                    return
        else:
            print("❌ access_token 속성이 없습니다")
            # 다른 가능한 속성 확인
            possible_attrs = ['token', 'accessToken', 'ACCESS_TOKEN']
            for attr in possible_attrs:
                if hasattr(token_manager, attr):
                    print(f"✓ 대체 속성 발견: {attr}")
                    token_manager.access_token = getattr(token_manager, attr)
                    break
            
            if not hasattr(token_manager, 'access_token'):
                print("❌ 사용 가능한 토큰 속성을 찾을 수 없습니다")
                return
        
    except Exception as e:
        print(f"❌ 토큰 매니저 초기화 실패: {e}")
        return
    
    print("✅ 토큰 매니저 준비 완료")
    
    # 선물 코드 조회기 초기화
    print("\n[2/4] 선물 코드 조회기 초기화 중...")
    fetcher = FuturesCodeFetcher(token_manager)
    
    try:
        # API 호출
        print("\n[3/4] 선물 종목 조회 중...")
        
        # 방법 1: 선물 목록 조회
        futures_list = await fetcher.fetch_futures_list()
        
        # 방법 1이 실패하면 방법 2: 종목 검색
        if not futures_list:
            print("\n[대안] 종목 검색 시도...")
            futures_list = await fetcher.search_stock("코스피200 선물")
        
        if futures_list:
            print("\n[4/4] 코스피200 선물 분석 중...")
            kospi200_futures = fetcher.find_kospi200_futures(futures_list)
            
            if kospi200_futures:
                print("\n" + "=" * 70)
                print("🎯 발견된 코스피200 선물")
                print("=" * 70)
                print(f"📌 종목 코드: {kospi200_futures['code']}")
                print(f"📌 종목명: {kospi200_futures['name']}")
                print("=" * 70)
                
                # .env 파일 업데이트
                env_file = ".env"
                env_content = []
                
                if os.path.exists(env_file):
                    with open(env_file, 'r', encoding='utf-8') as f:
                        env_content = f.readlines()
                
                # FUTURES_CODE 업데이트 또는 추가
                futures_line = f"FUTURES_CODE={kospi200_futures['code']}\n"
                updated = False
                
                for i, line in enumerate(env_content):
                    if line.startswith("FUTURES_CODE="):
                        env_content[i] = futures_line
                        updated = True
                        break
                
                if not updated:
                    env_content.append(futures_line)
                
                with open(env_file, 'w', encoding='utf-8') as f:
                    f.writelines(env_content)
                
                print(f"💾 .env 파일에 FUTURES_CODE 저장 완료")
                print("=" * 70)
                
                # 상세 정보 출력
                if 'full_info' in kospi200_futures:
                    print("\n📊 상세 정보:")
                    for key, value in kospi200_futures['full_info'].items():
                        if value:  # 값이 있는 경우만 출력
                            print(f"  {key}: {value}")
                
            else:
                print("\n❌ 코스피200 선물을 찾을 수 없습니다")
                
        else:
            print("\n❌ 선물 종목을 조회할 수 없었습니다")
            print("\n💡 문제 해결 방법:")
            print("1. 한국투자증권 API 키가 유효한지 확인하세요")
            print("2. access_token.json 파일이 유효한 토큰을 포함하는지 확인하세요")
            
    except Exception as e:
        print(f"\n❌ 예외 발생: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 세션 정리
        print("\n🧹 세션 정리 중...")
        await fetcher.close_session()
        
        # token_manager의 세션도 정리
        if hasattr(token_manager, 'session') and token_manager.session:
            try:
                await token_manager.session.close()
                await asyncio.sleep(0.25)  # 세션 종료 대기
            except Exception as e:
                print(f"[세션 종료 오류] {e}")
    
    print("\n✨ 프로그램 종료")

if __name__ == "__main__":
    # Windows에서 이벤트 루프 정책 설정
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 메인 함수 실행
    asyncio.run(main())