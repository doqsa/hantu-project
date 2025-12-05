# -*- coding: utf-8 -*-
"""
Korean Investment Securities Account Balance Query
Retrieves deposit balance and holdings information from trading account
"""
import requests
import json
import time
import urllib.parse
import os
from datetime import datetime, timedelta, timezone
from core.token_manage import TokenManager
from dotenv import load_dotenv

load_dotenv()

APP_KEY = os.getenv('APP_KEY')
APP_SECRET = os.getenv('APP_SECRET')
URL_BASE = 'https://openapivts.koreainvestment.com:29443'
TOKEN_FILE = "token-expire.json"
SECURITY_MARGIN = 60 * 10

# Account settings
CANO = "43407510"  # Account number (8 digits)
ACNT_PRDT_CD = "01"  # Account product code


def get_deposit_balance(token, app_key, cano, acnt_prdt_cd):
    """
    Query deposit balance and valuation amount for trading account using TTC8430R TR_ID.
    Retrieves total valuation amount which is crucial for NAV calculation.
    """
    print("\n[Query] Fetching account balance and valuation amount...")
    
    # API path for balance inquiry
    PATH = "/uapi/domestic-stock/v1/finance/inquire-balance"
    URL = URL_BASE + PATH
    
    # TR_ID for real trading (Use VTTC8430R for virtual trading)
    TR_ID = "TTC8430R"
    
    HEADERS = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": APP_SECRET,
        "tr_id": TR_ID,
        "custtype": "P"  # Personal account
    }
    
    # Parameters for TTC8430R TR_ID
    PARAMS = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "INQR_DVSN_1": "01",      # Balance division: '01' (all)
        "BSPR_ICLD_YN": "Y",      # Include securities
        "TR_CRF_YN": "N",         # Trading currency division (KRW)
        "INQR_DVSN_2": "00"       # Query division: '00' (all)
    }

    try:
        res = requests.get(URL, headers=HEADERS, params=PARAMS, timeout=10)
        response_data = res.json()
        
        print(f"[Response] Status: {res.status_code}")
        
        if res.status_code == 200 and response_data.get('rt_cd') == '0':
            print("[SUCCESS] Balance and valuation amount retrieved successfully")
            print("=" * 70)
            
            # Parse output2 (consolidated info)
            if response_data.get('output2') and len(response_data['output2']) > 0:
                cash_info = response_data['output2'][0]
                print("[Account Summary]")
                
                # Important fields from TTC8430R
                important_fields = {
                    'tot_evlu_amt': 'Total Valuation Amount',
                    'dnca_tot_amt': 'Total Deposit Amount (D+2)',
                    'total_pnl_amt': 'Total P&L Amount',
                }
                
                tot_evlu_amt = int(cash_info.get('tot_evlu_amt', '0'))
                six_percent = int(tot_evlu_amt * 0.06)
                
                for field, description in important_fields.items():
                    value = cash_info.get(field, '0')
                    print(f"    {description}: {int(value):>15,} KRW")
                    
                print(f"\n[Investment Amount Analysis (Based on Total Valuation)]")
                print(f"    Total Valuation Amount: {tot_evlu_amt:>15,} KRW")
                print(f"    6% Investment Amount:   {six_percent:>15,} KRW")
                print(f"    (Recommended max investment per trade)")
                
            # Parse output1 (holdings)
            if response_data.get('output1'):
                print(f"\n[Holdings] {len(response_data['output1'])} positions")
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
                    print(f"\n    Total Stock Valuation: {total_stock_value:>15,} KRW")
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
        print(f"[ERROR] Exception during balance query: {e}")
        return None


if __name__ == "__main__":
    print("=" * 70)
    print("[KIS Account Query Tool]")
    print(f"Token File: {TOKEN_FILE}")
    print(f"Account: {CANO}-{ACNT_PRDT_CD}")
    print("=" * 70)
    
    # Get token through token management system
    token_manager = TokenManager()
    final_token = token_manager.manage_token()
    
    if final_token:
        print(f"[Token] Successfully obtained: {final_token[:30]}...")
        
        # Query balance
        result = get_deposit_balance(final_token, APP_KEY, CANO, ACNT_PRDT_CD)
        
        if result:
            print("\n[SUCCESS] Account query completed successfully!")
            print("[Status] Program operating normally")
        else:
            print("\n[ERROR] Account query failed")
    else:
        print("[FATAL] Failed to obtain valid token. Program terminated.")
