"""Detect open (no-password) WiFi networks by parsing beacon frames."""
import requests, time

HOST = "192.168.1.102"

# Run tshark to get beacon frames with security info
cmd = "sudo /usr/local/bin/tshark -r /Users/crazydb911/$(ls -t /Users/crazydb911/wifiscan_*.pcap 2>/dev/null | head -1) -Y 'wlan && wlan.ssid' -T fields -e wlan.sa -e wlan.ssid -e wlan.mactype 2>&1 | head -50"

r = requests.post(
    f"http://{HOST}:8765/api/control/run",
    params={"cmd": cmd, "sudo": True, "timeout": 30},
    timeout=40
)
result = r.json()
print(f"Result: {result.get('ok')}")
print(f"Output:\n{result.get('output', '')[:2000]}")
