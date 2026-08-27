"""Check Windows app state."""
import requests, time

HOST = "192.168.1.107"

# Check state
print("Checking Windows state...")
r = requests.get(f"http://{HOST}:8766/api/state", timeout=10)
d = r.json()
print(f"Status: {d['status']}")
print(f"Message: {d['message']}")
print(f"Progress: {d['progress']}")

# Check log
print("\nLog (last 20 lines):")
r = requests.get(f"http://{HOST}:8766/api/log", timeout=10)
lines = r.json().get('lines', [])
for line in lines[-20:]:
    print(f"  {line}")
