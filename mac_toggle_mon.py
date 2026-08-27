"""WiFi toggle: use MONITOR mode to capture EAPOL from 32H9F_5G."""
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
cap=~/mon_cap.pcap
log=~/mon_cap.log
> $log

echo "START $(date)" >> $log
echo "SSID: $(networksetup -getairportnetwork en0 2>&1)" >> $log

# Create monitor interface
echo "Creating mon0 $(date)" >> $log
echo "$SUDO_PASS" | sudo -S ifconfig mon0 create 2>&1 >> $log
echo "$SUDO_PASS" | sudo -S ifconfig mon0 monu 2>&1 >> $log
echo "$SUDO_PASS" | sudo -S airport en0 -m 2>&1 >> $log
sleep 5

# Check if mon0 is up
echo "mon0 status: $(ifconfig mon0 2>&1 | head -3)" >> $log

# Start tshark on mon0 (monitor mode)
echo "Start tshark $(date)" >> $log
echo "$SUDO_PASS" | sudo -S /usr/local/bin/tshark -i mon0 -I -c 20000 -w $cap > /tmp/tshark_mon.log 2>&1 &
TP=$!
echo "tshark PID: $TP" >> $log
sleep 3

# Toggle WiFi (off then on to force re-association)
echo "OFF $(date)" >> $log
networksetup -setairportpower en0 off
sleep 10
echo "ON $(date)" >> $log
networksetup -setairportpower en0 on
sleep 15

# Wait for Mac to reconnect
for i in $(seq 1 10); do
    sleep 5
    NET=$(networksetup -getairportnetwork en0 2>&1)
    echo "  [wait $i] $NET" >> $log
    if echo "$NET" | grep -q "32H9F"; then
        echo "  CONNECTED" >> $log
        break
    fi
done

sleep 3
kill $TP 2>/dev/null
sleep 2
echo "$SUDO_PASS" | sudo -S chmod 644 $cap 2>/dev/null

# Clean up mon0
echo "$SUDO_PASS" | sudo -S ifconfig mon0 down 2>&1 >> $log
echo "$SUDO_PASS" | sudo -S ifconfig mon0 destroy 2>&1 >> $log

# Count EAPOL from 32H9F_5G (AP MAC: 6c:4f:89:4c:a0:e4)
EAPOL=$(/usr/local/bin/tshark -r $cap -Y 'eapol && (wlan.sa == 6c:4f:89:4c:a0:e4 || wlan.da == 6c:4f:89:4c:a0:e4)' 2>&1 | wc -l)
echo "EAPOL_COUNT (32H9F_5G): $EAPOL" >> $log
echo "AFTER: $(networksetup -getairportnetwork en0 2>&1)" >> $log
echo "DONE $(date)" >> $log
"""

sftp = client.open_sftp()
with sftp.open('/tmp/mon_toggle.sh', 'w') as f:
    f.write(script)
sftp.chmod('/tmp/mon_toggle.sh', 0o755)
sftp.close()
client.close()
print("Script uploaded. Starting...")

# Start
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)
stdin, stdout, stderr = client.exec_command("nohup bash /tmp/mon_toggle.sh > /dev/null 2>&1 &", timeout=10)
stdout.read()
client.close()

# Wait
print("Waiting (120s)...")
for i in range(30):
    time.sleep(5)
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(HOST, port=22, username=USER, pkey=key, timeout=10)
        stdin, stdout, stderr = client.exec_command("cat ~/mon_cap.log 2>/dev/null | tail -1", timeout=10)
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
    stdin, stdout, stderr = client.exec_command("cat ~/mon_cap.log 2>/dev/null", timeout=15)
    out = stdout.read().decode()
    print(f"\n=== LOG ===\n{out}")
    stdin, stdout, stderr = client.exec_command("/usr/local/bin/tshark -r ~/mon_cap.pcap -Y 'eapol && (wlan.sa == 6c:4f:89:4c:a0:e4 || wlan.da == 6c:4f:89:4c:a0:e4)' -T fields -e frame.number -e wlan.sa -e wlan.da 2>&1 | head -20", timeout=15)
    out = stdout.read().decode()
    print(f"\n=== EAPOL (32H9F_5G) ===\n{out}")
    client.close()
except Exception as e:
    print(f"Error: {e}")
