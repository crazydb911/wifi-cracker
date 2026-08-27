"""Debug Mac scan - check what tshark is capturing."""
import paramiko, time

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=10)

# Run tshark directly
print("Running tshark scan (10s)...")
cmd = f"echo '{SUDO_PASS}' | sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 300 -w /tmp/debug_scan.pcap 2>&1"
stdin, stdout, stderr = client.exec_command(cmd, timeout=20)
out = stdout.read().decode()
err = stderr.read().decode()
print(f"tshark output: {out[:500]}")
print(f"tshark error: {err[:500]}")

# Check file
print("\nChecking capture file...")
stdin, stdout, stderr = client.exec_command("ls -la /tmp/debug_scan.pcap 2>&1")
print(stdout.read().decode())

# Parse
print("Parsing beacons...")
cmd2 = "/usr/local/bin/tshark -r /tmp/debug_scan.pcap -Y 'wlan.mgt && wlan.ssid' -T fields -e wlan.sa -e wlan.ssid -e wlan.channel -e wlan.signal 2>&1 | head -20"
stdin, stdout, stderr = client.exec_command(cmd2, timeout=15)
print(stdout.read().decode())

# Check all frames
print("All frame types...")
cmd3 = "/usr/local/bin/tshark -r /tmp/debug_scan.pcap -T fields -e frame.type -e frame.protocols 2>&1 | head -20"
stdin, stdout, stderr = client.exec_command(cmd3, timeout=15)
print(stdout.read().decode())

client.close()
