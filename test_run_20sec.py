import asyncio
import subprocess
import time
import sys

print("[Test] Starting main.py for 20 seconds...")
proc = subprocess.Popen(
    [sys.executable, "main.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

try:
    for i in range(20):
        time.sleep(1)
        print(f"[{i+1}/20] Running...")
    
    proc.terminate()
    stdout, _ = proc.communicate(timeout=5)
    print("\n[Output from main.py]")
    lines = stdout.split('\n')
    for line in lines[-50:]:  # Print last 50 lines
        if line.strip():
            print(line)
except subprocess.TimeoutExpired:
    proc.kill()
    print("[Timeout] Killed process")
except KeyboardInterrupt:
    proc.terminate()
    print("[Interrupted]")
