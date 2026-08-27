"""Test Mac capture + upload."""
import requests, time

HOST = "192.168.1.102"
BSSID = "6c:4f:89:4c:a0:e4"
SSID = "32H9F_5G"
DURATION = 60

# Check state
print("Checking state...")
r = requests.get(f"http://{HOST}:8765/api/state", timeout=10)
d = r.json()
print(f"Status: {d['status']}")
print(f"WiFi: {d.get('win_status', 'n/a')}")

# Start capture
print(f"\nStarting capture ({DURATION}s)...")
r = requests.post(f"http://{HOST}:8765/api/capture?bssid={BSSID}&ssid={SSID}&duration={DURATION}", timeout=10)
print(f"Response: {r.json()}")

# Poll
print("\nPolling...")
for i in range(DURATION // 5 + 5):
    time.sleep(5)
    r = requests.get(f"http://{HOST}:8765/api/state", timeout=10)
    d = r.json()
    print(f"  [{(i+1)*5}s] {d['status']} - {d['message']}")
    if d['status'] == 'idle' and d.get('capture_file'):
        break

# Check result
print(f"\nCapture file: {d.get('capture_file')}")
print(f"EAPOL count: {d.get('capture_eapol_count', 0)}")
print(f"EAPOL target: {d.get('capture_eapol_target', 0)}")

# Upload
if d.get('capture_file'):
    print("\nUploading to Windows...")
    r = requests.post(f"http://{HOST}:8765/api/upload", timeout=10)
    print(f"Response: {r.json()}")
    
    # Poll upload
    for i in range(10):
        time.sleep(3)
        r = requests.get(f"http://{HOST}:8765/api/state", timeout=10)
        d = r.json()
        print(f"  [{(i+1)*3}s] {d['status']} - {d['message']}")
        if d['status'] == 'idle' and d.get('upload_status') == 'success':
            break
