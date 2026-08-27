"""Check if any EAPOL frames were captured (from any AP)."""
import requests

HOST = "192.168.1.102"

# Check all recent capture files for EAPOL
cmd = """
for f in /Users/crazydb911/cap_*.pcap; do
  count=$(sudo /usr/local/bin/tshark -r $f -Y 'eapol' 2>&1 | wc -l)
  if [ "$count" -gt 0 ]; then
    echo "$f: $count EAPOL frames"
  fi
done
"""

r = requests.post(
    f"http://{HOST}:8765/api/control/run",
    params={"cmd": cmd, "sudo": True, "timeout": 60},
    timeout=70
)
result = r.json()
print("EAPOL check:")
print(result.get('output', ''))

# Also check for any EAPOL in the most recent capture
cmd2 = "sudo /usr/local/bin/tshark -r /Users/crazydb911/cap_f8345a8c1f9f_1787845952.pcap -Y 'eapol' 2>&1 | head -20"

r = requests.post(
    f"http://{HOST}:8765/api/control/run",
    params={"cmd": cmd2, "sudo": True, "timeout": 30},
    timeout=40
)
result = r.json()
print("\nMost recent capture EAPOL:")
print(result.get('output', ''))
