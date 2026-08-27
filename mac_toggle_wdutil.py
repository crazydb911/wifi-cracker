"""WiFi toggle with wdutil scan + manual connect."""
import paramiko, time

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)

def ssh_cmd(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Write script
script = f"""#!/bin/bash
export SUDO_PASS=" "
cap=~/wdutil_cap.pcap
log=~/wdutil_cap.log
> $log

echo "START $(date)" >> $log
echo "SSID: $(networksetup -getairportnetwork en0 2>&1)" >> $log

# Start tshark
echo "$SUDO_PASS" | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 15000 -w $cap > /tmp/tshark_wd.log 2>&1 &
TP=$!
echo "tshark PID: $TP" >> $log
sleep 3

# Toggle OFF
echo "OFF $(date)" >> $log
networksetup -setairportpower en0 off
sleep 10

# Toggle ON
echo "ON $(date)" >> $log
networksetup -setairportpower en0 on
sleep 5

# Run wdutil scan to populate scan cache
echo "wdutil scan $(date)" >> $log
echo "$SUDO_PASS" | sudo -S wdutil scan 2>&1 >> $log

# Wait for scan to complete (check every 5s)
for i in $(seq 1 10); do
    sleep 5
    echo "  [scan $i x 5s]" >> $log
    # Check if 32H9F_5G is in scan results
    if echo "$SUDO_PASS" | sudo -S wdutil info 2>&1 | grep -q "32H9F_5G"; then
        echo "  FOUND 32H9F_5G in scan!" >> $log
        break
    fi
done

# Try to connect
echo "CONNECT $(date)" >> $log
networksetup -setairportnetwork en0 '32H9F_5G' 2>&1 >> $log

# Wait for connection
for i in $(seq 1 12); do
    sleep 5
    NET=$(networksetup -getairportnetwork en0 2>&1)
    echo "  [conn $i] $NET" >> $log
    if echo "$NET" | grep -q "32H9F"; then
        echo "  CONNECTED" >> $log
        break
    fi
done

sleep 3
kill $TP 2>/dev/null
sleep 2
echo "$SUDO_PASS" | sudo -S chmod 644 $cap 2>/dev/null

EAPOL=$(/usr/local/bin/tshark -r $cap -Y eapol 2>&1 | wc -l)
echo "EAPOL_COUNT: $EAPOL" >> $log
echo "AFTER: $(networksetup -getairportnetwork en0 2>&1)" >> $log
echo "DONE $(date)" >> $log
"""

sftp = client.open_sftp()
with sftp.open('/tmp/wdutil_toggle.sh', 'w') as f:
    f.write(script)
sftp.chmod('/tmp/wdutil_toggle.sh', 0o755)
sftp.close()
client.close()
print("Script uploaded. Starting...")

# Start
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)
stdin, stdout, stderr = client.exec_command("nohup bash /tmp/wdutil_toggle.sh > /dev/null 2>&1 &", timeout=10)
stdout.read()
client.close()

# Wait
print("Waiting (150s)...")
for i in range(40):
    time.sleep(5)
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(HOST, port=22, username=USER, pkey=key, timeout=10)
        stdin, stdout, stderr = client.exec_command("cat ~/wdutil_cap.log 2>/dev/null | tail -1", timeout=10)
        out = stdout.read().decode()
        client.close()
        if 'DONE' in out:
            print(f"Completed after {(i+1)*5}s")
            break
        print(f"  [{(i+1)*5}s] {out.strip()[:60]}")
    except:
        print(f"  [{(i+1)*5}s] Mac offline...")
else:
    print("Timeout")

# Read log
try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)
    stdin, stdout, stderr = client.exec_command("cat ~/wdutil_cap.log 2>/dev/null", timeout=15)
    out = stdout.read().decode()
    print(f"\n=== LOG ===\n{out}")
    stdin, stdout, stderr = client.exec_command("/usr/local/bin/tshark -r ~/wdutil_cap.pcap -Y eapol -T fields -e frame.number -e frame.time 2>&1 | head -20", timeout=15)
    out = stdout.read().decode()
    print(f"\n=== EAPOL ===\n{out}")
    client.close()
except Exception as e:
    print(f"Error: {e}")
