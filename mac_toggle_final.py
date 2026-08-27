"""Final WiFi toggle - capture + toggle + check EAPOL."""
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

# Write the script
script = f"""#!/bin/bash
export SUDO_PASS=" "
cap=~/final_cap.pcap
log=~/final_cap.log
> $log

echo "START $(date)" >> $log
echo "SSID: $(networksetup -getairportnetwork en0 2>&1)" >> $log

# Start tshark
echo "$SUDO_PASS" | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 10000 -w $cap > /tmp/tshark_final.log 2>&1 &
TP=$!
echo "tshark PID: $TP" >> $log
sleep 3

# Toggle WiFi (off for 10s)
echo "OFF $(date)" >> $log
networksetup -setairportpower en0 off
sleep 10

echo "ON $(date)" >> $log
networksetup -setairportpower en0 on
sleep 5

# Try to reconnect
SSID="32H9F_5G"
echo "Reconnecting to $SSID" >> $log
networksetup -setairportnetwork en0 "$SSID" 2>&1 >> $log

# Wait for reconnect (up to 60s)
for i in $(seq 1 12); do
    sleep 5
    NET=$(networksetup -getairportnetwork en0 2>&1)
    echo "  [$i x 5s] $NET" >> $log
    if echo "$NET" | grep -q "32H9F"; then
        echo "  CONNECTED" >> $log
        break
    fi
done

sleep 3
kill $TP 2>/dev/null
sleep 2
echo "$SUDO_PASS" | sudo -S chmod 644 $cap 2>/dev/null

# Count EAPOL
EAPOL=$(/usr/local/bin/tshark -r $cap -Y eapol 2>&1 | wc -l)
echo "EAPOL_COUNT: $EAPOL" >> $log
echo "AFTER: $(networksetup -getairportnetwork en0 2>&1)" >> $log
echo "DONE $(date)" >> $log
"""

sftp = client.open_sftp()
with sftp.open('/tmp/final_toggle.sh', 'w') as f:
    f.write(script)
sftp.chmod('/tmp/final_toggle.sh', 0o755)
sftp.close()
client.close()
print("Script uploaded. Starting (nohup)...")

# Start
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)
stdin, stdout, stderr = client.exec_command("nohup bash /tmp/final_toggle.sh > /dev/null 2>&1 &", timeout=10)
stdout.read()
client.close()

# Wait
print("Waiting for toggle to complete (90s)...")
for i in range(30):
    time.sleep(5)
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(HOST, port=22, username=USER, pkey=key, timeout=10)
        stdin, stdout, stderr = client.exec_command("cat ~/final_cap.log 2>/dev/null | tail -1", timeout=10)
        out = stdout.read().decode()
        client.close()
        if 'DONE' in out:
            print(f"Completed after {(i+1)*5}s")
            break
        print(f"  [{(i+1)*5}s] {out.strip()[:60]}")
    except:
        print(f"  [{(i+1)*5}s] Mac offline (WiFi toggle)...")
else:
    print("Timeout")

# Read log
try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)
    stdin, stdout, stderr = client.exec_command("cat ~/final_cap.log 2>/dev/null", timeout=15)
    out = stdout.read().decode()
    print(f"\n=== LOG ===\n{out}")
    stdin, stdout, stderr = client.exec_command("/usr/local/bin/tshark -r ~/final_cap.pcap -Y eapol -T fields -e frame.number -e frame.time 2>&1 | head -20", timeout=15)
    out = stdout.read().decode()
    print(f"\n=== EAPOL frames ===\n{out}")
    stdin, stdout, stderr = client.exec_command("/usr/local/bin/tshark -r ~/final_cap.pcap -T fields -e frame.protocols 2>&1 | sort | uniq -c | sort -rn | head -5", timeout=15)
    out = stdout.read().decode()
    print(f"\n=== Protocols ===\n{out}")
    client.close()
except Exception as e:
    print(f"Error: {e}")
