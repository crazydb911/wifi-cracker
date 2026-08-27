"""Debug Mac scan v3 - fix permissions."""
import paramiko, time

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=10)

# Capture
print("Capturing 10s...")
cmd = f"echo '{SUDO_PASS}' | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 200 -w /tmp/dbg3.pcap 2>&1"
stdin, stdout, stderr = client.exec_command(cmd, timeout=20)
print(stdout.read().decode()[:200])

# Fix permissions
print("Fixing permissions...")
cmd = f"echo '{SUDO_PASS}' | sudo -S cp /tmp/dbg3.pcap ~/dbg3.pcap && echo '{SUDO_PASS}' | sudo -S chmod 644 ~/dbg3.pcap"
stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
print(stdout.read().decode())

# Parse
print("Protocols:")
cmd = "/usr/local/bin/tshark -r ~/dbg3.pcap -T fields -e frame.protocols 2>&1 | sort | uniq -c | sort -rn | head -15"
stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
print(stdout.read().decode())

print("WLAN SSIDs:")
cmd = "/usr/local/bin/tshark -r ~/dbg3.pcap -Y wlan -T fields -e wlan.sa -e wlan.ssid 2>&1 | head -20"
stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
print(stdout.read().decode())

print("EAPOL:")
cmd = "/usr/local/bin/tshark -r ~/dbg3.pcap -Y eapol -T fields -e frame.number -e eapol.key.mic 2>&1 | head -10"
stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
print(stdout.read().decode())

client.close()
