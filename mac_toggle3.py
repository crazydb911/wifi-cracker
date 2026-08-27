"""WiFi toggle test v3 - disconnect via airport, check connection state."""
import paramiko, time

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=10)

def ssh(cmd, timeout=20):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Write script
script = """#!/bin/bash
export SUDO_PASS=" "
cap=~/toggle_test3.pcap

echo "=== BEFORE: WiFi state ==="
networksetup -getairportpower en0
networksetup -getairportnetwork en0
ifconfig en0 | grep -E 'status|inet'

echo ""
echo "=== Starting tshark ==="
echo "$SUDO_PASS" | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 5000 -w $cap > /tmp/tshark3.log 2>&1 &
TSHARK_PID=$!
sleep 3

echo "=== Toggling: airport -I en0 --setvht 0 ==="
echo "$SUDO_PASS" | sudo -S airport -I en0 --setvht 0 2>&1
sleep 2

echo "=== Toggling: setairportpower off ==="
networksetup -setairportpower en0 off
sleep 3

echo "=== MID: WiFi state ==="
networksetup -getairportpower en0
networksetup -getairportnetwork en0 2>&1
ifconfig en0 | grep -E 'status|inet'

echo "=== Waiting 12s ==="
sleep 12

echo "=== Toggling: setairportpower on ==="
networksetup -setairportpower en0 on
sleep 30

echo "=== AFTER: WiFi state ==="
networksetup -getairportpower en0
networksetup -getairportnetwork en0 2>&1
ifconfig en0 | grep -E 'status|inet'

echo ""
echo "=== Stopping tshark ==="
kill $TSHARK_PID 2>/dev/null
sleep 2
echo "$SUDO_PASS" | sudo -S chmod 644 $cap 2>/dev/null

echo "=== EAPOL count ==="
/usr/local/bin/tshark -r $cap -Y eapol -T fields -e frame.number -e frame.time 2>&1 | head -20
echo "Total EAPOL:"
/usr/local/bin/tshark -r $cap -Y eapol 2>&1 | wc -l

echo "=== Protocol summary ==="
/usr/local/bin/tshark -r $cap -T fields -e frame.protocols 2>&1 | sort | uniq -c | sort -rn | head -10

echo "=== tshark log ==="
cat /tmp/tshark3.log | head -5
echo "Done."
"""

sftp = client.open_sftp()
with sftp.open('/tmp/toggle_test3.sh', 'w') as f:
    f.write(script)
sftp.chmod('/tmp/toggle_test3.sh', 0o755)
sftp.close()

print("Running toggle test v3 (70s)...")
out, err = ssh("bash /tmp/toggle_test3.sh", timeout=100)
print(out)
if err:
    print(f"STDERR: {err[:500]}")

client.close()
