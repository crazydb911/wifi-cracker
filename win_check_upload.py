"""Check Windows upload endpoint."""
import requests

HOST = "192.168.1.107"

# Check if Windows app is running
r = requests.get(f"http://{HOST}:8766/api/state", timeout=10)
d = r.json()
print(f"Status: {d['status']}")
print(f"Message: {d['message']}")

# Check upload endpoint
r = requests.get(f"http://{HOST}:8766/", timeout=10)
print(f"\nRoot: {r.status_code}")

# Check if /api/upload exists
r = requests.post(f"http://{HOST}:8766/api/upload", timeout=10)
print(f"Upload: {r.status_code} - {r.text[:100]}")
