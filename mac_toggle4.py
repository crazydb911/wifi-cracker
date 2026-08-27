"""WiFi toggle v4 - use airport CLI (full path) + longer wait for reconnect."""
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

# First: find airport path
out, _ = ssh("which airport 2>/dev/null || find /usr/libexec -name airport 2>/dev/null || find /System/Library -name airport 2>/dev/null")
airport_path = out.strip().split('\n')[0] if out.strip() else "/usr/libexec/airportd"
print(f"airport path: {airport_path}")

# Check if Mac auto-connects
script = f"""#!/bin/bash
export SUDO_PASS=" "
cap=~/toggle_test4.pcap
AIRPORT="{airport_path}"

echo "=== BEFORE ==="
networksetup -getairportnetwork en0
ifconfig en0 | grep -E 'status|inet '

echo "=== Starting tshark ==="
echo "$SUDO_PASS" | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 8000 -w $cap > /tmp/tshark4.log 2>&1 &
TSHARK_PID=$!
sleep 3

echo "=== OFF ==="
networksetup -setairportpower en0 off
sleep 10

echo "=== ON ==="
networksetup -setairportpower en0 on

# Wait for Mac to reconnect (check every 5s for up to 40s)
for i in $(seq 1 8); do
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
networksetup -getairportnetwork en0
ifconfig en0 | grep -E 'status|inet '

echo "=== Stopping tshark ==="
kill $TSHARK_PID 2>/dev/null
sleep 2
echo "$SUDO_PASS" | sudo -S chmod 644 $cap 2>/dev/null

echo "=== EAPOL ==="
/usr/local/bin/tshark -r $cap -Y eapol -T fields -e frame.number -e frame.time 2>&1 | head -20
echo "Total:"
/usr/local/bin/tshark -r $cap -Y eapol 2>&1 | wc -l

echo "=== Protocols ==="
/usr/local/bin/tshark -r $cap -T fields -e frame.protocols 2>&1 | sort | uniq -c | sort -rn | head -10
echo "Done."
"""

sftp = client.open_sftp()
with sftp.open('/tmp/toggle_test4.sh', 'w') as f:
    f.write(script)
sftp.chmod('/tmp/toggle_test4.sh', 0o755)
sftp.close()

print("Running toggle test v4 (90s)...")
out, err = ssh("bash /tmp/toggle_test4.sh", timeout=120)
print(out)
if err:
    print(f"STDERR: {err[:500]}")

client.close()
