import asyncio
import json
from core.token_manage import TokenManager

async def test():
    tm = TokenManager()
    token = tm.manage_token()
    
    print("[Test] Fetching full iNAV response...")
    
    import aiohttp
    url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": "YOUR_APP_KEY",  # Will be loaded from env by aiohttp
        "appsecret": "YOUR_APP_SECRET",
        "tr_id": "FHKST01010100"
    }
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "069500"}
    
    try:
        async with aiohttp.ClientSession() as session:
            # Need to load from env
            import os
            from dotenv import load_dotenv
            load_dotenv()
            headers["appkey"] = os.getenv('APP_KEY')
            headers["appsecret"] = os.getenv('APP_SECRET')
            
            async with session.get(url, headers=headers, params=params) as resp:
                data = await resp.json()
                print(f"[Full Output]")
                print(json.dumps(data.get('output', {}), indent=2, ensure_ascii=False)[:800])
    except Exception as e:
        print(f"[Exception] {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())


