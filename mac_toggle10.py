"""WiFi toggle v10 - find exact SSID name + use it for reconnect."""
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

# Get exact SSID
out, _ = ssh("networksetup -getairportnetwork en0 2>&1")
# Parse: "Current Wi-Fi Network: XXXX"
ssid = out.strip().split(':')[-1].strip()
print(f"Exact SSID: '{ssid}'")

# Also check with airport
out, _ = ssh(f"echo '{SUDO_PASS}' | sudo -S /System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport -I en0 2>&1 | head -10")
print(f"\nairport info:\n{out}")

# Try reconnect with exact name
print(f"\n=== Reconnecting to '{ssid}' ===")
ssh("networksetup -setairportpower en0 off")
time.sleep(5)
ssh("networksetup -setairportpower en0 on")
time.sleep(3)
out, err = ssh(f"networksetup -setairportnetwork en0 '{ssid}' 2>&1", timeout=30)
print(f"setairportnetwork: {out.strip()} {err.strip()}")

# Wait
for i in range(8):
    time.sleep(5)
    out, _ = ssh("networksetup -getairportnetwork en0 2>&1")
    print(f"  [{(i+1)*5}s] {out.strip()}")
    if '32H9F' in out:
        print("  Connected!")
        break

client.close()
