"""Check if 192.168.1.115 is Mac."""
import paramiko

HOST = "192.168.1.115"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=10)

def ssh(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Check OS
out, _ = ssh("uname -a")
print(f"OS: {out.strip()}")

# Check WiFi
out, _ = ssh("networksetup -getairportnetwork en0 2>&1")
print(f"WiFi: {out.strip()}")

# Check IP
out, _ = ssh("ifconfig en0 | grep 'inet '")
print(f"IP: {out.strip()}")

# Check hostname
out, _ = ssh("hostname")
print(f"Hostname: {out.strip()}")

client.close()
