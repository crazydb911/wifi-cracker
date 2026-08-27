"""Check Mac state + deploy LAN control."""
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

# Check state
out, _ = ssh("networksetup -getairportnetwork en0 2>&1")
print(f"WiFi: {out.strip()}")
out, _ = ssh("ifconfig en0 | grep -E 'status|inet '")
print(f"Interface: {out.strip()}")

# Check if Mac app is running
out, _ = ssh("curl -s http://127.0.0.1:8765/api/state 2>&1 | head -5")
print(f"Mac app: {out.strip()[:100]}")

# Check if final_toggle.sh exists
out, _ = ssh("ls -la /tmp/final_toggle.sh ~/final_toggle.log 2>/dev/null")
print(f"Toggle script: {out.strip()}")

client.close()
print("\nMac is online!")
