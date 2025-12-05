import asyncio
from core.token_manage import TokenManager
from balance_fetcher import BalanceFetcher

async def main():
    queue = asyncio.Queue()
    token_mgr = TokenManager()
    fetcher = BalanceFetcher(token_mgr, queue)
    
    print("[Test] Running balance fetcher...")
    result = await fetcher.fetch_balance()
    print(f"[Result] {result}")

if __name__ == "__main__":
    asyncio.run(main())
