"""WiFi toggle: deauth (kill association) instead of full power off.
This keeps the radio on so tshark can capture the EAPOL handshake."""
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
cap=~/deauth_cap.pcap
log=~/deauth_cap.log
> $log

echo "START $(date)" >> $log
echo "SSID: $(networksetup -getairportnetwork en0 2>&1)" >> $log

# Get BSSID of current network
BSSID=$(ifconfig en0 | grep -A5 'ether' | grep -o '[0-9a-f:]{17}' | head -1)
echo "BSSID: $BSSID" >> $log

# Start tshark (radio stays ON)
echo "$SUDO_PASS" | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 15000 -w $cap > /tmp/tshark_deauth.log 2>&1 &
TP=$!
echo "tshark PID: $TP" >> $log
sleep 3

# Method 1: Kill DHCP lease (forces reassociation)
echo "Method 1: Kill DHCP $(date)" >> $log
echo "$SUDO_PASS" | sudo -S killall -9 dhclient 2>&1 >> $log
sleep 5

# Check if still connected
NET=$(networksetup -getairportnetwork en0 2>&1)
echo "  After kill dhclient: $NET" >> $log

# Method 2: Use airport to disconnect (if available)
echo "Method 2: airport disconnect $(date)" >> $log
AIRPORT="/System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport"
echo "$SUDO_PASS" | sudo -S $AIRPORT -I en0 2>&1 | head -5 >> $log

# Method 3: Toggle just the association (not power)
echo "Method 3: networksetup disconnect $(date)" >> $log
# Try using the hidden "setairportnetwork" with empty to disconnect
networksetup -setairportnetwork en0 '32H9F_5G' 2>&1 >> $log

# Wait for reconnection
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

EAPOL=$(/usr/local/bin/tshark -r $cap -Y eapol 2>&1 | wc -l)
echo "EAPOL_COUNT: $EAPOL" >> $log
echo "AFTER: $(networksetup -getairportnetwork en0 2>&1)" >> $log
echo "DONE $(date)" >> $log
"""

sftp = client.open_sftp()
with sftp.open('/tmp/deauth_toggle.sh', 'w') as f:
    f.write(script)
sftp.chmod('/tmp/deauth_toggle.sh', 0o755)
sftp.close()
client.close()
print("Script uploaded. Starting...")

# Start
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)
stdin, stdout, stderr = client.exec_command("nohup bash /tmp/deauth_toggle.sh > /dev/null 2>&1 &", timeout=10)
stdout.read()
client.close()

# Wait
print("Waiting (90s)...")
for i in range(25):
    time.sleep(5)
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(HOST, port=22, username=USER, pkey=key, timeout=10)
        stdin, stdout, stderr = client.exec_command("cat ~/deauth_cap.log 2>/dev/null | tail -1", timeout=10)
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
    stdin, stdout, stderr = client.exec_command("cat ~/deauth_cap.log 2>/dev/null", timeout=15)
    out = stdout.read().decode()
    print(f"\n=== LOG ===\n{out}")
    stdin, stdout, stderr = client.exec_command("/usr/local/bin/tshark -r ~/deauth_cap.pcap -Y eapol -T fields -e frame.number -e frame.time 2>&1 | head -20", timeout=15)
    out = stdout.read().decode()
    print(f"\n=== EAPOL ===\n{out}")
    client.close()
except Exception as e:
    print(f"Error: {e}")
