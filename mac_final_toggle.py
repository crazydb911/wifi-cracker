"""Final approach: capture + toggle in one script, nohup, read log after."""
import paramiko, time, socket

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "

def connect():
    key = paramiko.Ed25519Key.from_private_key_file(KEY)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=22, username=USER, pkey=key, timeout=15)
    return c

def ssh(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Connect
print("Connecting to Mac...")
client = connect()
out, _ = ssh(client, "networksetup -getairportnetwork en0 2>&1")
print(f"WiFi: {out.strip()}")

# Write the capture+toggle script
script = f"""#!/bin/bash
export SUDO_PASS=" "
cap=~/final_toggle.pcap
log=~/final_toggle.log
> $log

echo "START $(date)" >> $log
echo "SSID: $(networksetup -getairportnetwork en0 2>&1)" >> $log

# Start tshark
echo "$SUDO_PASS" | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 10000 -w $cap > /tmp/tshark_final.log 2>&1 &
TP=$!
echo "tshark PID: $TP" >> $log
sleep 3

# Toggle WiFi
echo "OFF" >> $log
networksetup -setairportpower en0 off
sleep 8
echo "ON" >> $log
networksetup -setairportpower en0 on
sleep 5

# Try to reconnect with exact SSID
SSID=$(networksetup -getairportnetwork en0 2>&1 | grep -o '32H9F.*' | head -1)
if [ -z "$SSID" ]; then
    SSID="32H9F_5G"
fi
echo "Reconnecting to: $SSID" >> $log
networksetup -setairportnetwork en0 "$SSID" 2>&1 >> $log

# Wait for reconnect
for i in $(seq 1 12); do
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

# Count EAPOL
echo "EAPOL: $(/usr/local/bin/tshark -r $cap -Y eapol 2>&1 | wc -l)" >> $log
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

# Start with nohup (reconnect)
client = connect()
ssh(client, "nohup bash /tmp/final_toggle.sh > /dev/null 2>&1 &", timeout=10)
client.close()

# Wait for Mac to come back (it will be offline during toggle)
print("Waiting for Mac...")
for i in range(40):
    time.sleep(5)
    try:
        client = connect()
        out, _ = ssh(client, "cat ~/final_toggle.log 2>/dev/null | tail -1", timeout=10)
        if 'DONE' in out:
            print(f"Completed after {(i+1)*5}s")
            break
        print(f"  [{(i+1)*5}s] {out.strip()[:60]}")
        client.close()
    except:
        print(f"  [{(i+1)*5}s] Mac offline (WiFi toggle)...")
else:
    print("Timeout")

# Read full log
try:
    client = connect()
    out, _ = ssh(client, "cat ~/final_toggle.log 2>/dev/null", timeout=15)
    print(f"\n=== LOG ===\n{out}")
    # Check EAPOL
    out, _ = ssh(client, "/usr/local/bin/tshark -r ~/final_toggle.pcap -Y eapol -T fields -e frame.number -e frame.time 2>&1 | head -20", timeout=15)
    print(f"\n=== EAPOL frames ===\n{out}")
    out, _ = ssh(client, "/usr/local/bin/tshark -r ~/final_toggle.pcap -T fields -e frame.protocols 2>&1 | sort | uniq -c | sort -rn | head -5", timeout=15)
    print(f"\n=== Protocols ===\n{out}")
    client.close()
except Exception as e:
    print(f"Error: {e}")
