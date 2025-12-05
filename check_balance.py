import json
import requests
from dotenv import load_dotenv
import os

load_dotenv()

with open('access_token.json', 'r') as f:
    token_data = json.load(f)
    access_token = token_data.get('access_token')

print(f'[Token] {access_token[:30]}...')

URL = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/finance/inquire-balance'
TR_ID = 'TQSBI0305'

headers = {
    'Content-Type': 'application/json',
    'authorization': f'Bearer {access_token}',
    'appkey': os.getenv('APP_KEY'),
    'appsecret': os.getenv('APP_SECRET'),
    'tr_id': TR_ID,
    'custtype': 'P'
}

params = {
    'CANO': '43407510',
    'ACNT_PRDT_CD': '01',
    'INQR_DVSN_1': '01',
    'BSPR_ICLD_YN': 'Y',
    'TR_CRF_YN': 'N',
    'INQR_DVSN_2': '00'
}

res = requests.get(URL, headers=headers, params=params, verify=False)
print(f'[Status] {res.status_code}')
print(f'[Response (first 500 chars)] {res.text[:500]}')

if res.status_code == 200:
    try:
        data = res.json()
        print(f'[JSON Parsed] rt_cd={data.get("rt_cd")}')
        
        if data.get('rt_cd') == '0':
            print('[SUCCESS] Account accessible!')
            if data.get('output2'):
                cash = data['output2'][0]
                tot_evlu = int(cash.get('tot_evlu_amt', 0))
                dnca = int(cash.get('dnca_tot_amt', 0))
                pnl = int(cash.get('total_pnl_amt', 0))
                print(f'[Total Evaluation] {tot_evlu:,} KRW')
                print(f'[Deposit] {dnca:,} KRW')
                print(f'[P&L] {pnl:,} KRW')
        else:
            msg = data.get('msg1', 'Unknown error')
            print(f'[API Error] {msg}')
    except Exception as e:
        print(f'[Parse Exception] {e}')
else:
    print(f'[HTTP Error] Status {res.status_code}')
