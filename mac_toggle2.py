"""WiFi toggle test - use nohup for tshark."""
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

# Write a script to Mac that does everything
script = """#!/bin/bash
export SUDO_PASS=" "
cap=~/toggle_test.pcap

echo "Starting tshark..."
echo "$SUDO_PASS" | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 5000 -w $cap > /tmp/tshark_toggle.log 2>&1 &
TSHARK_PID=$!
echo "tshark PID: $TSHARK_PID"
sleep 3

echo "WiFi OFF..."
networksetup -setairportpower en0 off
sleep 15

echo "WiFi ON..."
networksetup -setairportpower en0 on
sleep 25

echo "Stopping tshark..."
kill $TSHARK_PID 2>/dev/null
sleep 2

echo "Fixing permissions..."
echo "$SUDO_PASS" | sudo -S chmod 644 $cap 2>/dev/null

echo "Counting EAPOL..."
/usr/local/bin/tshark -r $cap -Y eapol -T fields -e frame.number 2>&1 | wc -l

echo "Protocol summary:"
/usr/local/bin/tshark -r $cap -T fields -e frame.protocols 2>&1 | sort | uniq -c | sort -rn | head -5

echo "Done."
"""

# Upload and run
sftp = client.open_sftp()
with sftp.open('/tmp/toggle_test.sh', 'w') as f:
    f.write(script)
sftp.chmod('/tmp/toggle_test.sh', 0o755)
sftp.close()

print("Running toggle test (60s)...")
out, err = ssh("bash /tmp/toggle_test.sh", timeout=90)
print(out)
if err:
    print(f"STDERR: {err[:500]}")

client.close()
