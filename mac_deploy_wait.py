"""Deploy Mac app (wait for Mac to come back)."""
import paramiko, time, socket

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "

key = paramiko.Ed25519Key.from_private_key_file(KEY)

# Wait for Mac
print("Waiting for Mac...")
for i in range(30):
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

# Connect
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)

def ssh(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Kill old app
print("Killing old app...")
ssh("pkill -f wifi_cracker_v6.py 2>/dev/null; sleep 2")

# Upload app
print("Uploading app...")
sftp = client.open_sftp()
local = r"C:\Users\crazydb911\Documents\deepseek\mac_wifi_cracker_v6.py"
remote = "/Users/crazydb911/wifi_cracker_v6.py"
sftp.put(local, remote)
sftp.close()

# Write start script
start_script = """#!/bin/bash
cd /Users/crazydb911
nohup python3 wifi_cracker_v6.py > wifi_cracker_v6.log 2>&1 &
echo $! > wifi_cracker_v6.pid
echo "Started with PID $(cat wifi_cracker_v6.pid)"
"""

sftp = client.open_sftp()
with sftp.open('/Users/crazydb911/start_v6.sh', 'w') as f:
    f.write(start_script)
sftp.chmod('/Users/crazydb911/start_v6.sh', 0o755)
sftp.close()

# Start app
print("Starting app...")
out, err = ssh("bash /Users/crazydb911/start_v6.sh")
print(f"{out.strip()} {err.strip()}")

# Wait
time.sleep(3)

# Verify
out, _ = ssh("curl -s http://127.0.0.1:8765/api/state 2>&1 | head -3")
print(f"\nVerify: {out.strip()[:100]}")

# Check WiFi
out, _ = ssh("curl -s http://127.0.0.1:8765/api/wifi 2>&1")
print(f"WiFi: {out.strip()}")

client.close()
print("\nDone!")
