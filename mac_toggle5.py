"""WiFi toggle v5 - find airport CLI + manual connect + check EAPOL."""
import paramiko, time

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=10)

def ssh(cmd, timeout=20):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Find airport CLI
out, _ = ssh("ls /System/Library/PrivateFrameworks/Apple80211.framework/Resources/ 2>/dev/null | head -5")
print(f"Apple80211 resources: {out.strip()}")
out, _ = ssh("ls /usr/libexec/ 2>/dev/null | grep -i air")
print(f"air in /usr/libexec: {out.strip()}")
out, _ = ssh("find / -name 'airport' -type f 2>/dev/null | head -5", timeout=15)
print(f"airport files: {out.strip()}")

# Check saved WiFi profiles
out, _ = ssh("networksetup -listallnetworkservices 2>&1")
print(f"\nNetwork services:\n{out}")

# Check if 32H9F_5G is saved
out, _ = ssh("ls ~/Library/Preferences/SystemConfiguration/ 2>/dev/null")
print(f"\nSystemConfig files:\n{out}")

# Try to reconnect manually
print("\n=== Reconnecting to 32H9F_5G ===")
out, _ = ssh("networksetup -setairportpower en0 off")
time.sleep(3)
out, _ = ssh("networksetup -setairportpower en0 on")
time.sleep(10)
out, _ = ssh("networksetup -getairportnetwork en0 2>&1")
print(f"After 10s: {out.strip()}")

# Try to manually connect
out, err = ssh("networksetup -setairportnetwork en0 '32H9F_5G' 2>&1", timeout=30)
print(f"setairportnetwork: {out.strip()} {err.strip()}")
time.sleep(15)
out, _ = ssh("networksetup -getairportnetwork en0 2>&1")
print(f"After manual connect: {out.strip()}")

client.close()
