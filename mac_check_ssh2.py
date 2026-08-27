"""Check Mac SSH (Codex says it works)."""
import paramiko, time

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)

def ssh(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Check current state
out, _ = ssh("networksetup -getairportnetwork en0 2>&1")
print(f"WiFi: {out.strip()}")
out, _ = ssh("ifconfig en0 | grep -E 'status|inet '")
print(f"Interface: {out.strip()}")

# Check Mac app
out, _ = ssh("ps aux | grep wifi_cracker | grep -v grep")
print(f"\nMac app: {out.strip()}")

# Check Mac app log
out, _ = ssh("tail -20 ~/wifi_cracker_v6.log 2>/dev/null")
print(f"\nMac app log:\n{out}")

# Check Mac app API
out, _ = ssh("curl -s http://127.0.0.1:8765/api/state 2>&1 | head -3")
print(f"\nMac app API: {out.strip()[:100]}")

# Check WiFi API
out, _ = ssh("curl -s http://127.0.0.1:8765/api/wifi 2>&1")
print(f"\nWiFi API: {out.strip()}")

client.close()
print("\nDone!")
