# -*- coding: utf-8 -*-
"""
Simple Account Balance Query - No Async Required
"""
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

APP_KEY = os.getenv('APP_KEY')
APP_SECRET = os.getenv('APP_SECRET')
URL_BASE = 'https://openapivts.koreainvestment.com:29443'

# Account settings
CANO = "43407510"
ACNT_PRDT_CD = "01"

def get_token():
    """Get access token from token file (pre-existing)"""
    try:
        if os.path.exists('token-expire.json'):
            with open('token-expire.json', 'r') as f:
                data = json.load(f)
                token = data.get('access_token')
                expires_in = data.get('expires_in', 0)
                
                if token:
                    print(f"[Token] Loaded from file: {token[:30]}...")
                    return token
    except Exception as e:
        print(f"[Error] Token file read failed: {e}")
    
    return None

def get_deposit_balance(token, app_key, cano, acnt_prdt_cd):
    """Query deposit balance and valuation amount"""
    print("\n[Query] Querying account balance...")
    
    # API endpoint
    PATH = "/uapi/domestic-stock/v1/finance/inquire-balance"
    URL = URL_BASE + PATH
    
    # TR_ID for balance query
    TR_ID = "TQSBI0305"  # Simulation mode balance query
    
    HEADERS = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": APP_SECRET,
        "tr_id": TR_ID,
        "custtype": "P"
    }
    
    # Query parameters
    PARAMS = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "INQR_DVSN_1": "01",
        "BSPR_ICLD_YN": "Y",
        "TR_CRF_YN": "N",
        "INQR_DVSN_2": "00"
    }

    try:
        res = requests.get(URL, headers=HEADERS, params=PARAMS, timeout=10, verify=False)
        response_data = res.json()
        
        print(f"[Response] Status: {res.status_code}")
        
        if res.status_code == 200 and response_data.get('rt_cd') == '0':
            print("[SUCCESS] Balance query successful!")
            print("=" * 70)
            
            # Parse output2 (account summary)
            if response_data.get('output2') and len(response_data['output2']) > 0:
                cash_info = response_data['output2'][0]
                print("\n[Account Summary]")
                
                fields = {
                    'tot_evlu_amt': 'Total Valuation Amount',
                    'dnca_tot_amt': 'Deposit Total Amount (D+2)',
                    'total_pnl_amt': 'Total P&L Amount',
                    'nmnc_amt': 'Cash Amount',
                }
                
                tot_evlu_amt = int(cash_info.get('tot_evlu_amt', '0'))
                six_percent = int(tot_evlu_amt * 0.06)
                
                for field, description in fields.items():
                    value = cash_info.get(field, '0')
                    print(f"    {description:.<40} {int(value):>15,} KRW")
                    
                print(f"\n[Investment Analysis (Based on Total Valuation)]")
                print(f"    Total Valuation Amount:............ {tot_evlu_amt:>15,} KRW")
                print(f"    6% Investment Amount:............. {six_percent:>15,} KRW")
                print(f"    (Recommended max investment per trade)")
                
            # Parse output1 (holdings)
            if response_data.get('output1'):
                print(f"\n[Holdings] {len(response_data['output1'])} stocks held")
                total_stock_value = 0
                for i, stock in enumerate(response_data['output1'], 1):
                    stock_qty = int(stock.get('hldg_qty', 0))
                    stock_value = int(stock.get('evlu_amt', 0))
                    
                    if stock_qty > 0:
                        print(f"    {i:2d}. {stock.get('prdt_name', 'N/A')}")
                        print(f"        Code: {stock.get('pdno', 'N/A')}")
                        print(f"        Quantity: {stock_qty:>8} shares")
                        print(f"        Valuation: {stock_value:>8,} KRW")
                        total_stock_value += stock_value
                
                if total_stock_value > 0:
                    print(f"\n    Total Stock Valuation: {total_stock_value:>25,} KRW")
            else:
                print("\n[Holdings] No stocks held")
                
            print("=" * 70)
            return response_data
        else:
            error_msg = response_data.get('msg1', 'API Error')
            print(f"[ERROR] Balance query failed: {error_msg}")
            print(f"   Error Code: {response_data.get('rt_cd')}, TR_ID: {TR_ID}")
            return None

    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return None


if __name__ == "__main__":
    print("=" * 70)
    print("[KIS Account Query Tool - Simple Version]")
    print(f"Account: {CANO}-{ACNT_PRDT_CD}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Get token from file
    final_token = get_token()
    
    if final_token:
        # Query balance
        result = get_deposit_balance(final_token, APP_KEY, CANO, ACNT_PRDT_CD)
        
        if result:
            print("\n[SUCCESS] Account query completed!")
        else:
            print("\n[ERROR] Account query failed")
    else:
        print("[FATAL] No token available. Run main.py first to generate token file.")
