"""Check MAC addresses in pcap."""
import paramiko

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

# Check EAPOL frame MACs
out, _ = ssh_cmd("/usr/local/bin/tshark -r ~/sudo_cap.pcap -Y eapol -T fields -e wlan.sa -e wlan.da -e wlan.bssid 2>&1")
print(f"=== EAPOL frame MACs ===\n{out}")

# Check all wlan frames (first 10)
out, _ = ssh_cmd("/usr/local/bin/tshark -r ~/sudo_cap.pcap -Y wlan -T fields -e wlan.sa -e wlan.da 2>&1 | head -10")
print(f"=== First 10 wlan frames ===\n{out}")

# Check if there are any 802.11 frames with valid MACs
out, _ = ssh_cmd("/usr/local/bin/tshark -r ~/sudo_cap.pcap -Y 'wlan && wlan.sa != 00:00:00:00:00:00' -T fields -e wlan.sa -e wlan.da 2>&1 | head -5")
print(f"=== Frames with valid src MAC ===\n{out}")

client.close()
