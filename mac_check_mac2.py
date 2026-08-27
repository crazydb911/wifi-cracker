"""Check Mac state + try airport -I en0 --setpower 0."""
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
out, _ = ssh_cmd("ifconfig en0 | grep -E 'status|inet '")
print(f"Interface: {out.strip()}")

# Try airport -I en0 --setpower 0
AIRPORT = "/System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport"
print("\n=== airport -I en0 --setpower 0 ===")
out, err = ssh_cmd(f"echo '{SUDO_PASS}' | sudo -S {AIRPORT} -I en0 --setpower 0 2>&1", timeout=20)
print(f"setpower 0: {out.strip()} {err.strip()}")
time.sleep(3)

out, _ = ssh_cmd("networksetup -getairportnetwork en0 2>&1")
print(f"After setpower 0: {out.strip()}")

# Try airport -I en0 --setpower 1
print("\n=== airport -I en0 --setpower 1 ===")
out, err = ssh_cmd(f"echo '{SUDO_PASS}' | sudo -S {AIRPORT} -I en0 --setpower 1 2>&1", timeout=20)
print(f"setpower 1: {out.strip()} {err.strip()}")
time.sleep(5)

out, _ = ssh_cmd("networksetup -getairportnetwork en0 2>&1")
print(f"After setpower 1: {out.strip()}")

client.close()
