"""WiFi toggle v9 - check if Mac reconnected + read toggle8 log."""
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

# Check WiFi state
out, _ = ssh("networksetup -getairportnetwork en0 2>&1")
print(f"WiFi: {out.strip()}")
out, _ = ssh("ifconfig en0 | grep -E 'status|inet '")
print(f"Interface: {out.strip()}")

# Read toggle8 log
out, _ = ssh("cat /tmp/toggle8.log 2>/dev/null")
print(f"\n=== toggle8.log ===\n{out}")

# Check if toggle8 capture exists
out, _ = ssh("ls -la ~/toggle8.pcap 2>/dev/null")
print(f"\nCapture: {out.strip()}")

# If capture exists, check EAPOL
if out.strip():
    out, _ = ssh("/usr/local/bin/tshark -r ~/toggle8.pcap -Y eapol 2>&1 | wc -l")
    print(f"EAPOL count: {out.strip()}")
    out, _ = ssh("/usr/local/bin/tshark -r ~/toggle8.pcap -T fields -e frame.protocols 2>&1 | sort | uniq -c | sort -rn | head -5")
    print(f"Protocols:\n{out}")

client.close()
