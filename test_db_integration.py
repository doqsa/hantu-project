import asyncio
import subprocess
import time
import sys
import aiomysql
import os
from dotenv import load_dotenv

load_dotenv()

async def check_db_records():
    """Check database tables for new records"""
    try:
        conn = await aiomysql.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '3306')),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            db=os.getenv('DB_NAME', 'trading_db')
        )
        
        async with conn.cursor() as cur:
            tables = {
                'kodex200_trade': 'SELECT COUNT(*) as cnt FROM kodex200_trade',
                'kodex200_hoga': 'SELECT COUNT(*) as cnt FROM kodex200_hoga',
                'market_exchange': 'SELECT COUNT(*) as cnt FROM market_exchange',
                'kodex200_nav': 'SELECT COUNT(*) as cnt FROM kodex200_nav'
            }
            
            print("\n" + "="*60)
            print("[Database Record Count]")
            print("="*60)
            for table_name, query in tables.items():
                try:
                    await cur.execute(query)
                    result = await cur.fetchone()
                    count = result[0] if result else 0
                    print(f"  {table_name:20s}: {count:6d} records")
                except Exception as e:
                    print(f"  {table_name:20s}: [ERROR] {e}")
            
            # Show recent records from trade table
            print("\n[Recent Trade Data (last 5)]")
            try:
                await cur.execute("""
                    SELECT bsop_date, check_time, stck_cntg_qty, stck_prpr 
                    FROM kodex200_trade 
                    ORDER BY id DESC LIMIT 5
                """)
                rows = await cur.fetchall()
                for row in rows:
                    print(f"  {row}")
            except:
                pass
            
            # Show recent exchange rate
            print("\n[Recent Exchange Rate (last 1)]")
            try:
                await cur.execute("""
                    SELECT timestamp, usd_krw 
                    FROM market_exchange 
                    ORDER BY id DESC LIMIT 1
                """)
                row = await cur.fetchone()
                if row:
                    print(f"  {row}")
            except:
                pass
            
        conn.close()
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"[DB Error] {e}")

async def main():
    print("[Test] Starting main.py for 30 seconds...")
    
    # Start main.py
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    try:
        # Let system warm up
        await asyncio.sleep(3)
        
        # Check records periodically
        for i in range(6):  # Check 6 times (every 5 seconds for 30 seconds)
            print(f"\n>>> Check #{i+1} at {time.strftime('%H:%M:%S')}")
            await check_db_records()
            
            if i < 5:
                await asyncio.sleep(5)
        
        print("[Test] Stopping system...")
        proc.terminate()
        
        # Collect output
        stdout, _ = proc.communicate(timeout=5)
        print("\n[System Output (last 30 lines)]")
        lines = stdout.split('\n')
        for line in lines[-30:]:
            if line.strip():
                print(line)
                
    except subprocess.TimeoutExpired:
        proc.kill()
        print("[Timeout] Killed process")
    except KeyboardInterrupt:
        proc.terminate()
        print("[Interrupted]")

if __name__ == "__main__":
    asyncio.run(main())
