"""Check beacon frames (fixed filter)."""
import requests

HOST = "192.168.1.102"

# Check beacon frames (use simpler filter)
cmd = "sudo /usr/local/bin/tshark -r /Users/crazydb911/wifiscan_1787844590.pcap -Y 'wlan && wlan.ssid' -T fields -e wlan.sa -e wlan.ssid 2>&1 | head -30"

r = requests.post(
    f"http://{HOST}:8765/api/control/run",
    params={"cmd": cmd, "sudo": True, "timeout": 30},
    timeout=40
)
result = r.json()
print("Beacon frames:")
print(result.get('output', ''))
