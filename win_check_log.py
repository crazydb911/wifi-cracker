"""Check Windows log for extraction results."""
import requests

HOST = "192.168.1.107"

# Check log
r = requests.get(f"http://{HOST}:8766/api/log", timeout=10)
lines = r.json().get('lines', [])
print("Windows log (last 30 lines):")
for line in lines[-30:]:
    print(f"  {line}")
