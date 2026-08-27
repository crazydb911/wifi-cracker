"""Check Mac state after setpower toggle."""
import paramiko, time, socket

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "

# Wait for Mac
for i in range(20):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    r = s.connect_ex((HOST, 22))
    s.close()
    if r == 0:
        print(f"Mac back after {(i+1)*5}s!")
        break
    time.sleep(5)
else:
    print("Mac still offline")
    exit()

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

# Read setpower log
out, _ = ssh_cmd("cat ~/setpower_cap.log 2>/dev/null")
print(f"\n=== setpower_cap.log ===\n{out}")

client.close()
