"""Check WiFi security (correct fields)."""
import requests

HOST = "192.168.1.102"

# Check for RSN/WPA info (correct field names)
cmd = "sudo /usr/local/bin/tshark -r /Users/crazydb911/wifiscan_1787844590.pcap -Y 'wlan && wlan.ssid' -T fields -e wlan.sa -e wlan.ssid -e wlan.rsn.cap.auth_alg -e wlan.wpa.cap.auth_alg 2>&1 | head -30"

r = requests.post(
    f"http://{HOST}:8765/api/control/run",
    params={"cmd": cmd, "sudo": True, "timeout": 30},
    timeout=40
)
result = r.json()
print("WiFi security info:")
print(result.get('output', ''))
