"""Check which WiFi networks are open (parse capabilities)."""
import requests, re

HOST = "192.168.1.102"

# Get all beacon frames with capabilities
cmd = "sudo /usr/local/bin/tshark -r /Users/crazydb911/wifiscan_1787844590.pcap -Y 'wlan && wlan.ssid' -V 2>&1"

r = requests.post(
    f"http://{HOST}:8765/api/control/run",
    params={"cmd": cmd, "sudo": True, "timeout": 60},
    timeout=70
)
result = r.json()
output = result.get('output', '')

# Parse capabilities (look for "Privacy: Data confidentiality required")
ap_map = {}
lines = output.split('\n')
current_bssid = None
current_ssid = None

for line in lines:
    # Extract BSSID
    if 'Source address:' in line and 'Transmitter address' not in line:
        match = re.search(r'\(([\w:]+)\)', line)
        if match:
            current_bssid = match.group(1)
    
    # Extract SSID
    if 'SSID:' in line and '"' in line:
        match = re.search(r'SSID: "([^"]+)"', line)
        if match:
            current_ssid = match.group(1)
    
    # Check privacy bit
    if 'Privacy:' in line and current_bssid:
        privacy = 'Data confidentiality required' in line
        if current_bssid not in ap_map:
            ap_map[current_bssid] = {
                'bssid': current_bssid,
                'ssid': current_ssid,
                'privacy': privacy
            }

print(f"Found {len(ap_map)} networks:\n")
for bssid, info in ap_map.items():
    security = "WPA2 (encrypted)" if info['privacy'] else "Open (no password)"
    print(f"{info['ssid']} ({bssid}): {security}")
