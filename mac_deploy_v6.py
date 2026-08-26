#!/usr/bin/env python3
"""Deploy Mac WiFi Cracker v6 to Mac via SSH."""
import paramiko, time

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
    
    # Check WiFi
    stdin, stdout, stderr = client.exec_command("networksetup -getairportpower en0")
    result = stdout.read().decode().strip()
    print(f"WiFi power: {result}")
    
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
    start_script = """#!/bin/bash
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
    out = stdout.read().decode().strip()
    print(out)
    
    time.sleep(3)
    
    # Check log
    stdin, stdout, stderr = client.exec_command("cat /Users/crazydb911/wifi_cracker_v6.log 2>/dev/null | head -10")
    log = stdout.read().decode().strip()
    print(f"Log: {log}")
    
    client.close()
    print(f"\nMac app deployed! Visit http://{HOST}:8765")

if __name__ == "__main__":
    main()
