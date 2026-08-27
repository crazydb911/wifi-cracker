"""Debug Mac scan v2 - check what's in the capture."""
import paramiko, time

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=10)

# Run tshark scan
print("Capturing 10s...")
cmd = f"echo '{SUDO_PASS}' | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 200 -w /tmp/dbg2.pcap 2>&1"
stdin, stdout, stderr = client.exec_command(cmd, timeout=20)
print(stdout.read().decode()[:200])

# Check what protocols are in the capture
print("\nProtocols in capture:")
cmd = "/usr/local/bin/tshark -r /tmp/dbg2.pcap -T fields -e frame.protocols 2>&1 | sort | uniq -c | sort -rn | head -20"
stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
print(stdout.read().decode())

# Check for EAPOL
print("EAPOL frames:")
cmd = "/usr/local/bin/tshark -r /tmp/dbg2.pcap -Y eapol 2>&1 | head -10"
stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
print(stdout.read().decode())

# Check for wlan frames with SSID
print("WLAN frames with SSID:")
cmd = "/usr/local/bin/tshark -r /tmp/dbg2.pcap -Y wlan -T fields -e wlan.sa -e wlan.ssid 2>&1 | head -20"
stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
print(stdout.read().decode())

client.close()
