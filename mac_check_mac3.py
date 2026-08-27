"""Check why Mac shows 32H9F (2.4G) instead of 32H9F_5G."""
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
print(f"WiFi: {out.strip()}")

# Check IP
out, _ = ssh_cmd("ifconfig en0 | grep 'inet '")
print(f"IP: {out.strip()}")

# Check which network (2.4G or 5G)
# 32H9F_5G BSSID: 6c:4f:89:4c:a0:e4
# 32H9F BSSID: ?
out, _ = ssh_cmd("echo '{SUDO_PASS}' | sudo -S /System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport -I en0 2>&1".replace('{SUDO_PASS}', SUDO_PASS))
print(f"\nairport info:\n{out}")

client.close()
