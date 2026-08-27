"""Check why setairportnetwork can't find 32H9F_5G."""
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

# Check current state
out, _ = ssh_cmd("networksetup -getairportnetwork en0 2>&1")
print(f"Current: {out.strip()}")

# List visible networks
print("\n=== Visible networks (tshark 5s) ===")
cap = "/tmp/scan_check.pcap"
out, _ = ssh_cmd(f"echo '{SUDO_PASS}' | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 200 -w {cap} 2>&1", timeout=15)
print(out.strip()[:100])

# Parse SSIDs
out, _ = ssh_cmd(f"/usr/local/bin/tshark -r {cap} -Y wlan -T fields -e wlan.sa -e wlan.ssid 2>&1 | sort -u | head -20")
print(f"\nSSIDs:\n{out}")

# Check saved profiles
print("\n=== Saved WiFi profiles ===")
out, _ = ssh_cmd("ls ~/Library/Preferences/SystemConfiguration/ 2>/dev/null")
print(out)

# Try connecting to a different network first (to test if setairportnetwork works)
print("\n=== Test: connect to 32H9F (2.4G) ===")
out, _ = ssh_cmd("networksetup -setairportnetwork en0 '32H9F' 2>&1", timeout=20)
print(f"32H9F: {out.strip()}")
time.sleep(10)
out, _ = ssh_cmd("networksetup -getairportnetwork en0 2>&1")
print(f"Now: {out.strip()}")

# Switch back to 32H9F_5G
print("\n=== Switch to 32H9F_5G ===")
out, _ = ssh_cmd("networksetup -setairportnetwork en0 '32H9F_5G' 2>&1", timeout=20)
print(f"32H9F_5G: {out.strip()}")
time.sleep(10)
out, _ = ssh_cmd("networksetup -getairportnetwork en0 2>&1")
print(f"Now: {out.strip()}")

client.close()
