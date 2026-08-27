"""Test Mac capture 60s."""
import requests, time

base = 'http://192.168.1.102:8765'

# Scan
print("Scanning...")
r = requests.post(f'{base}/api/scan?duration=10', timeout=30)
time.sleep(12)
d = requests.get(f'{base}/api/state').json()
target = next((a for a in d.get('ap_list', []) if '32H9F' in a['ssid']), None)
if not target:
    print('32H9F not found!')
    exit(1)
print(f'Target: {target["ssid"]} ({target["bssid"]})')

# Capture 60s
print('Capturing 60s...')
r = requests.post(f'{base}/api/capture?bssid={target["bssid"]}&ssid={target["ssid"]}&duration=60', timeout=90)
time.sleep(62)
d = requests.get(f'{base}/api/state').json()
print(f'Result: {d["message"]}')
print(f'EAPOL: {d.get("capture_eapol_count", "?")}')

# Upload
print('Uploading...')
r = requests.post(f'{base}/api/upload', timeout=120)
time.sleep(15)
d = requests.get(f'{base}/api/state').json()
print(f'Upload: {d.get("upload_status")}')
print(f'Win: {d.get("win_message")}')
