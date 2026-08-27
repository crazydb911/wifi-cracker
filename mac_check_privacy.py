"""Check which WiFi networks are open (no privacy bit)."""
import requests

HOST = "192.168.1.102"

# Check privacy bit in capabilities (if privacy bit is set, network is encrypted)
cmd = "sudo /usr/local/bin/tshark -r /Users/crazydb911/wifiscan_1787844590.pcap -Y 'wlan && wlan.ssid' -T fields -e wlan.sa -e wlan.ssid -e wlan.cap.privacy 2>&1 | sort | uniq"

r = requests.post(
    f"http://{HOST}:8765/api/control/run",
    params={"cmd": cmd, "sudo": True, "timeout": 30},
    timeout=40
)
result = r.json()
print("WiFi privacy status (1=encrypted, 0=open):")
print(result.get('output', ''))
