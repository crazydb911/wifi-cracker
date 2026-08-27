"""Check WiFi security (dump all fields)."""
import requests

HOST = "192.168.1.102"

# Dump all fields for one beacon frame
cmd = "sudo /usr/local/bin/tshark -r /Users/crazydb911/wifiscan_1787844590.pcap -Y 'wlan && wlan.ssid' -V 2>&1 | head -100"

r = requests.post(
    f"http://{HOST}:8765/api/control/run",
    params={"cmd": cmd, "sudo": True, "timeout": 30},
    timeout=40
)
result = r.json()
print("Beacon frame details (first 100 lines):")
print(result.get('output', ''))
