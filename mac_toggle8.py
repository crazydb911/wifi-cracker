"""WiFi toggle v8 - simple: capture + toggle + check. Mac is back now."""
import paramiko, time

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)

def ssh(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Write a simple script
script = """#!/bin/bash
export SUDO_PASS=" "
cap=~/toggle8.pcap
log=/tmp/toggle8.log
> $log

echo "BEFORE: $(networksetup -getairportnetwork en0 2>&1)" >> $log

# Start tshark
echo "$SUDO_PASS" | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 8000 -w $cap > /tmp/tshark8.log 2>&1 &
TP=$!
sleep 3

# Toggle
networksetup -setairportpower en0 off
sleep 8
networksetup -setairportpower en0 on
sleep 5
networksetup -setairportnetwork en0 '32H9F_5G' 2>&1 >> $log

# Wait for reconnect
for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 5
    NET=$(networksetup -getairportnetwork en0 2>&1)
    echo "  [$i] $NET" >> $log
    if echo "$NET" | grep -q "32H9F"; then
        echo "  CONNECTED" >> $log
        break
    fi
done

sleep 3
kill $TP 2>/dev/null
sleep 2
echo "$SUDO_PASS" | sudo -S chmod 644 $cap 2>/dev/null

echo "EAPOL_COUNT: $(/usr/local/bin/tshark -r $cap -Y eapol 2>&1 | wc -l)" >> $log
echo "AFTER: $(networksetup -getairportnetwork en0 2>&1)" >> $log
echo "DONE" >> $log
"""

sftp = client.open_sftp()
with sftp.open('/tmp/toggle8.sh', 'w') as f:
    f.write(script)
sftp.chmod('/tmp/toggle8.sh', 0o755)
sftp.close()

print("Running toggle v8 (nohup)...")
ssh("nohup bash /tmp/toggle8.sh > /dev/null 2>&1 &", timeout=10)

# Poll for completion
for i in range(25):
    time.sleep(5)
    try:
        out, _ = ssh("cat /tmp/toggle8.log 2>/dev/null | tail -1", timeout=10)
        if 'DONE' in out:
            print(f"Completed after {(i+1)*5}s")
            break
    except:
        print(f"  [{(i+1)*5}s] Mac temporarily offline (WiFi toggle)...")
else:
    print("Timeout")

# Read log
try:
    out, _ = ssh("cat /tmp/toggle8.log 2>/dev/null", timeout=15)
    print(f"\n=== LOG ===\n{out}")
except:
    print("Mac still offline")

client.close()
