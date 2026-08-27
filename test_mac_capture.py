"""Test Mac capture for 32H9F_5G."""
import requests, time

base = 'http://192.168.1.102:8765'

# Get state
d = requests.get(f'{base}/api/state').json()
print(f"APs: {len(d.get('ap_list', []))}")
for ap in d.get('ap_list', [])[:5]:
    print(f"  {ap['ssid']} ({ap['bssid']})")

# Find 32H9F_5G
target = None
for ap in d.get('ap_list', []):
    if '32H9F' in ap['ssid']:
        target = ap
        print(f"\nTarget: {target['ssid']} ({target['bssid']})")
        break

if not target:
    print("\n32H9F_5G not found in scan!")
    exit(1)

# Capture 30s
print(f"\nCapturing {target['ssid']} for 30s...")
r = requests.post(f"{base}/api/capture?bssid={target['bssid']}&ssid={target['ssid']}&duration=30", timeout=60)
print(f"Capture started: {r.json()}")

# Wait
time.sleep(35)
d = requests.get(f'{base}/api/state').json()
print(f"\nResult: {d['message']}")
print(f"File: {d.get('capture_file')}")
print(f"EAPOL: {d.get('capture_eapol_count', '?')}")
