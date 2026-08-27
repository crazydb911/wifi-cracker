"""Check Mac HTTP (fast)."""
import requests

HOST = "192.168.1.102"

print("Checking Mac HTTP (8765)...")
try:
    r = requests.get(f'http://{HOST}:8765/api/state', timeout=5)
    print(f"HTTP: {r.status_code} - {r.json().get('status', 'unknown')}")
except Exception as e:
    print(f"HTTP: {str(e)[:100]}")
