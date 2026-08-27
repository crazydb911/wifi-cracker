"""Test full Mac → Windows flow."""
import requests, time

mac_base = 'http://192.168.1.102:8765'
win_base = 'http://192.168.1.107:8766'

# 1. Scan
print("1. Scanning...")
r = requests.post(f'{mac_base}/api/scan?duration=10', timeout=30)
time.sleep(12)
d = requests.get(f'{mac_base}/api/state').json()
print(f"   Found {len(d.get('ap_list', []))} APs")

# 2. Find 32H9F_5G
target = None
for ap in d.get('ap_list', []):
    if '32H9F' in ap['ssid']:
        target = ap
        break
if not target:
    print("   32H9F_5G not found!")
    exit(1)
print(f"   Target: {target['ssid']} ({target['bssid']})")

# 3. Capture 30s (no EAPOL expected without reconnect)
print(f"2. Capturing 30s...")
r = requests.post(f"{mac_base}/api/capture?bssid={target['bssid']}&ssid={target['ssid']}&duration=30", timeout=60)
time.sleep(32)
d = requests.get(f'{mac_base}/api/state').json()
print(f"   {d['message']}")
print(f"   EAPOL: {d.get('capture_eapol_count', '?')}")

# 4. Upload to Windows
print("3. Uploading to Windows...")
r = requests.post(f'{mac_base}/api/upload', timeout=120)
time.sleep(15)
d = requests.get(f'{mac_base}/api/state').json()
print(f"   Upload: {d.get('upload_status')}")
print(f"   Win status: {d.get('win_status')}")
print(f"   Win message: {d.get('win_message')}")

# 5. Check Windows
print("4. Checking Windows...")
d = requests.get(f'{win_base}/api/state').json()
print(f"   Status: {d['status']}")
print(f"   Message: {d['message']}")
print(f"   Hashes: {d['hash_count']}")
print(f"   SSID: {d.get('ssid')}")
print(f"   GPU: {d.get('gpu_temp')}C")

print("\nDone!")
