"""WiFi toggle v7 - nohup + read log file."""
import paramiko, time

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "
AIRPORT = "/System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport"

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)

def ssh(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Write script that outputs to a file
script = f"""#!/bin/bash
export SUDO_PASS=" "
AIRPORT="{AIRPORT}"
cap=~/toggle_test7.pcap
log=/tmp/toggle7.log
> $log

echo "=== BEFORE ===" >> $log
networksetup -getairportnetwork en0 2>&1 >> $log
ifconfig en0 | grep -E 'status|inet ' >> $log

echo "=== Starting tshark ===" >> $log
echo "$SUDO_PASS" | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 8000 -w $cap > /tmp/tshark7.log 2>&1 &
TSHARK_PID=$!
echo "tshark PID: $TSHARK_PID" >> $log
sleep 3

echo "=== OFF ===" >> $log
networksetup -setairportpower en0 off
sleep 8

echo "=== ON ===" >> $log
networksetup -setairportpower en0 on
sleep 3

echo "=== airport info ===" >> $log
echo "$SUDO_PASS" | sudo -S $AIRPORT -I en0 2>&1 >> $log

echo "=== setairportnetwork ===" >> $log
networksetup -setairportnetwork en0 '32H9F_5G' 2>&1 >> $log

for i in $(seq 1 10); do
    sleep 5
    NET=$(networksetup -getairportnetwork en0 2>&1)
    echo "  [${i}x5s] $NET" >> $log
    if echo "$NET" | grep -q "32H9F"; then
        echo "  Connected!" >> $log
        break
    fi
done

sleep 5
echo "=== AFTER ===" >> $log
networksetup -getairportnetwork en0 2>&1 >> $log
ifconfig en0 | grep -E 'status|inet ' >> $log

echo "=== Stopping tshark ===" >> $log
kill $TSHARK_PID 2>/dev/null
sleep 2
echo "$SUDO_PASS" | sudo -S chmod 644 $cap 2>/dev/null

echo "=== EAPOL ===" >> $log
/usr/local/bin/tshark -r $cap -Y eapol -T fields -e frame.number -e frame.time -e eapol.type 2>&1 >> $log
echo "Total EAPOL:" >> $log
/usr/local/bin/tshark -r $cap -Y eapol 2>&1 | wc -l >> $log

echo "=== Protocols ===" >> $log
/usr/local/bin/tshark -r $cap -T fields -e frame.protocols 2>&1 | sort | uniq -c | sort -rn | head -10 >> $log
echo "Done." >> $log
"""

sftp = client.open_sftp()
with sftp.open('/tmp/toggle_test7.sh', 'w') as f:
    f.write(script)
sftp.chmod('/tmp/toggle_test7.sh', 0o755)
sftp.close()

# Run with nohup
print("Starting toggle test v7 (nohup, 100s)...")
ssh("nohup bash /tmp/toggle_test7.sh > /dev/null 2>&1 &", timeout=10)

# Wait for completion
for i in range(25):
    time.sleep(5)
    out, _ = ssh("cat /tmp/toggle7.log 2>/dev/null | tail -1", timeout=10)
    last = out.strip()
    if 'Done.' in last:
        print(f"Completed after {(i+1)*5}s")
        break
    print(f"  [{(i+1)*5}s] waiting... last: {last[:60]}")

# Read full log
out, _ = ssh("cat /tmp/toggle7.log 2>/dev/null", timeout=15)
print("\n=== LOG ===")
print(out)

client.close()
