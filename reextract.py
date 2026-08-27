"""Re-extract the sudo_cap.pcap with fixed extractor."""
import requests

pcap = r"C:\Users\crazydb911\Documents\deepseek\sudo_cap.pcap"

with open(pcap, 'rb') as f:
    r = requests.post(
        'http://127.0.0.1:8766/api/extract',
        files={'file': ('sudo_cap.pcap', f, 'application/octet-stream')},
        data={'ssid': '32H9F_5G'},
        timeout=30
    )
print(f"Upload: {r.json()}")

import time
time.sleep(5)
r = requests.get('http://127.0.0.1:8766/api/state', timeout=5)
d = r.json()
print(f"\nStatus: {d['status']}")
print(f"Message: {d['message']}")
print(f"Hash count: {d['hash_count']}")
print(f"Hash file: {d['hash_file']}")
print(f"Nonce issues: {d.get('nonce_issues', 'N/A')}")
if d['hash_file']:
    with open(d['hash_file']) as f:
        for line in f:
            print(f"  {line.strip()[:100]}...")
