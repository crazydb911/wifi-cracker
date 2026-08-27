"""Check EAPOL frames (fix sudo password)."""
import requests

HOST = "192.168.1.102"

# Check EAPOL in most recent capture (use echo for sudo password)
cmd = """
echo ' ' | sudo -S /usr/local/bin/tshark -r /Users/crazydb911/cap_f8345a8c1f9f_1787845952.pcap -Y 'eapol' -T fields -e frame.number -e eapol.type -e wlan.sa -e wlan.da 2>&1
"""

r = requests.post(
    f"http://{HOST}:8765/api/control/run",
    params={"cmd": cmd, "sudo": True, "timeout": 30},
    timeout=40
)
result = r.json()
print("EAPOL frames in most recent capture:")
print(result.get('output', ''))
