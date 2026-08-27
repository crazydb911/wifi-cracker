"""Check Windows log for recent extractions."""
import requests

HOST = "192.168.1.107"

# Check log
r = requests.get(f"http://{HOST}:8766/api/log", timeout=10)
lines = r.json().get('lines', [])
print("Windows log (last 50 lines):")
for line in lines[-50:]:
    print(f"  {line}")
