"""Check which WiFi networks are open (no password)."""
import requests

HOST = "192.168.1.102"

# Get AP list
r = requests.get(f"http://{HOST}:8765/api/state", timeout=10)
d = r.json()
ap_list = d['ap_list']

print(f"Checking {len(ap_list)} networks for open (no-password) status:\n")

for ap in ap_list:
    ssid = ap['ssid']
    bssid = ap['bssid']
    # Check security type (if available)
    security = ap.get('security', 'unknown')
    print(f"{ssid} ({bssid}): {security}")

# Try to connect to each network to check if open
print("\nTrying to connect to each network...")

for i, ap in enumerate(ap_list):
    ssid = ap['ssid']
    bssid = ap['bssid']
    
    print(f"\n[{i+1}/{len(ap_list)}] {ssid} ({bssid})")
    
    # Run networksetup to check
    r = requests.post(
        f"http://{HOST}:8765/api/control/run",
        params={"cmd": f"networksetup -listpreferredwirelessnetworks en0 | grep -A5 '{ssid}'", "sudo": False},
        timeout=10
    )
    result = r.json()
    if result.get('ok') and result.get('output'):
        print(f"  {result['output'].strip()}")
    else:
        print(f"  Not in preferred networks (might be open)")
