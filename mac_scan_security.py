"""Scan WiFi with security info."""
import requests, time

HOST = "192.168.1.102"

# Start scan
print("Scanning WiFi (10s)...")
r = requests.post(f"http://{HOST}:8765/api/scan?duration=10", timeout=10)
print(f"Response: {r.json()}")

# Wait for scan
time.sleep(15)

# Get results
r = requests.get(f"http://{HOST}:8765/api/state", timeout=10)
d = r.json()
print(f"\nStatus: {d['status']}")
print(f"Found {len(d['ap_list'])} networks:\n")

for i, ap in enumerate(d['ap_list']):
    print(f"{i+1}. {ap['ssid']} ({ap['bssid']})")
    print(f"   Security: {ap.get('security', 'unknown')}")
    print(f"   Channel: {ap.get('channel', '?')}")
    print(f"   RSSI: {ap.get('rssi', '?')}")
    print()
