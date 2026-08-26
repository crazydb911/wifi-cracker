#!/usr/bin/env python3
"""Deploy Mac WiFi Cracker v6 to Mac via SSH."""
import paramiko, time, sys

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
LOCAL_APP = r"C:\Users\crazydb911\Documents\deepseek\mac_wifi_cracker_v6.py"
REMOTE_APP = "/Users/crazydb911/wifi_cracker_v6.py"

def main():
    print("Connecting to Mac...")
    key = paramiko.Ed25519Key.from_private_key_file(KEY)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=22, username=USER, pkey=key, timeout=10)
    print("Connected!")
    
    # Check if Mac WiFi is on
    stdin, stdout, stderr = client.exec_command("networksetup -getairportpower en0")
    result = stdout.read().decode().strip()
    print(f"WiFi power: {result}")
    
    if result != "Wi-Fi Power On":
        print("WiFi is OFF, turning on...")
        client.exec_command("sudo -S networksetup -setairportpower en0 on", stdin=True)
        time.sleep(5)
    
    # Kill old app
    print("Killing old app...")
    client.exec_command("pkill -f wifi_cracker || true")
    time.sleep(2)
    
    # Upload new app
    print(f"Uploading {LOCAL_APP} -> {REMOTE_APP}")
    sftp = client.open_sftp()
    sftp.put(LOCAL_APP, REMOTE_APP)
    sftp.close()
    
    # Create start script
    print("Creating start script...")
    start_script = f"""#!/bin/bash
cd /Users/crazydb911
nohup python3 wifi_cracker_v6.py > wifi_cracker_v6.log 2>&1 &
echo $! > wifi_cracker_v6.pid
echo "Started PID $(cat wifi_cracker_v6.pid)"
"""
    sftp = client.open_sftp()
    with sftp.open("/Users/crazydb911/start_v6.sh", 'w') as f:
        f.write(start_script)
    sftp.chmod("/Users/crazydb911/start_v6.sh", 0o755)
    sftp.close()
    
    # Start app
    print("Starting app...")
    stdin, stdout, stderr = client.exec_command("bash /Users/crazydb911/start_v6.sh")
    print(stdout.read().decode().strip())
    
    time.sleep(3)
    
    # Check if it's running
    stdin, stdout, stderr = client.exec_command("cat /Users/crazydb911/wifi_cracker_v6.log | head -5")
    print(f"Log: {stdout.read().decode().strip()}")
    
    client.close()
    print(f"\n✅ Mac app deployed! Visit http://{HOST}:8765")

if __name__ == "__main__":
    main()
