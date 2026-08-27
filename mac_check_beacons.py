"""Check beacon frames for security info."""
import requests, time

HOST = "192.168.1.102"

# List recent pcap files
r = requests.post(
    f"http://{HOST}:8765/api/control/run",
    params={"cmd": "ls -lt /Users/crazydb911/wifiscan_*.pcap 2>/dev/null | head -5", "sudo": False},
    timeout=10
)
result = r.json()
print("Recent pcap files:")
print(result.get('output', ''))

# Check beacon frames in most recent pcap
cmd = "ls -t /Users/crazydb911/wifiscan_*.pcap 2>/dev/null | head -1"
r = requests.post(
    f"http://{HOST}:8765/api/control/run",
    params={"cmd": cmd, "sudo": False},
    timeout=10
)
result = r.json()
pcap_file = result.get('output', '').strip()
print(f"\nMost recent: {pcap_file}")

# Check beacon frames
if pcap_file:
    cmd2 = f"sudo /usr/local/bin/tshark -r {pcap_file} -Y 'wlan && wlan.fc.type_or_subtype == 8' -T fields -e wlan.sa -e wlan.ssid 2>&1 | head -20"
    r = requests.post(
        f"http://{HOST}:8765/api/control/run",
        params={"cmd": cmd2, "sudo": True, "timeout": 30},
        timeout=40
    )
    result = r.json()
    print(f"\nBeacon frames:")
    print(result.get('output', ''))
