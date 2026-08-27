"""WiFi toggle v6 - use airport CLI + manual connect + capture EAPOL."""
import paramiko, time

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "
AIRPORT = "/System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport"

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=10)

def ssh(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Write script
script = f"""#!/bin/bash
export SUDO_PASS=" "
AIRPORT="{AIRPORT}"
cap=~/toggle_test6.pcap

echo "=== BEFORE ==="
networksetup -getairportnetwork en0 2>&1
ifconfig en0 | grep -E 'status|inet '

echo "=== Starting tshark ==="
echo "$SUDO_PASS" | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 8000 -w $cap > /tmp/tshark6.log 2>&1 &
TSHARK_PID=$!
sleep 3

echo "=== OFF ==="
networksetup -setairportpower en0 off
sleep 8

echo "=== ON ==="
networksetup -setairportpower en0 on
sleep 3

echo "=== Manual connect: airport --enableschedoff ==="
echo "$SUDO_PASS" | sudo -S $AIRPORT -I en0 2>&1 | head -5

echo "=== setairportnetwork ==="
networksetup -setairportnetwork en0 '32H9F_5G' 2>&1

# Wait for connection
for i in $(seq 1 10); do
    sleep 5
    NET=$(networksetup -getairportnetwork en0 2>&1)
    echo "  [${{i}}x5s] $NET"
    if echo "$NET" | grep -q "32H9F"; then
        echo "  Connected!"
        break
    fi
done

sleep 5

echo "=== AFTER ==="
networksetup -getairportnetwork en0 2>&1
ifconfig en0 | grep -E 'status|inet '

echo "=== Stopping tshark ==="
kill $TSHARK_PID 2>/dev/null
sleep 2
echo "$SUDO_PASS" | sudo -S chmod 644 $cap 2>/dev/null

echo "=== EAPOL ==="
/usr/local/bin/tshark -r $cap -Y eapol -T fields -e frame.number -e frame.time -e eapol.type 2>&1 | head -30
echo "Total EAPOL:"
/usr/local/bin/tshark -r $cap -Y eapol 2>&1 | wc -l

echo "=== Protocols ==="
/usr/local/bin/tshark -r $cap -T fields -e frame.protocols 2>&1 | sort | uniq -c | sort -rn | head -10
echo "Done."
"""

sftp = client.open_sftp()
with sftp.open('/tmp/toggle_test6.sh', 'w') as f:
    f.write(script)
sftp.chmod('/tmp/toggle_test6.sh', 0o755)
sftp.close()

print("Running toggle test v6 (100s)...")
out, err = ssh("bash /tmp/toggle_test6.sh", timeout=130)
print(out)
if err:
    print(f"STDERR: {err[:500]}")

client.close()
