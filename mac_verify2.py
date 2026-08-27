"""Verify Mac app v7."""
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

# Check if running
out, _ = ssh("ps aux | grep wifi_cracker | grep -v grep")
print(f"Process: {out.strip()}")

# Check log
out, _ = ssh("tail -20 ~/wifi_cracker_v6.log 2>/dev/null")
print(f"\nLog:\n{out}")

# Check port
out, _ = ssh("curl -s http://127.0.0.1:8765/api/state 2>&1")
print(f"\nAPI: {out.strip()[:200]}")

# Check WiFi
out, _ = ssh("curl -s http://127.0.0.1:8765/api/wifi 2>&1")
print(f"\nWiFi: {out.strip()}")

client.close()
