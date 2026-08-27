#!/usr/bin/env python3
"""設定 Mac SSH key"""
import paramiko
import os
import sys

# Mac 資訊
MAC_HOST = "192.168.1.102"
MAC_USER = "crazydb911"
MAC_PASS = os.environ.get("MAC_PASSWORD", "crazydb911")

# Public key
pub_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDuecEMHgnHrIcoGGbhM5bP+5iSlVYnrk+7wVJHSg/eq opremote@DESKTOP-IL11VJ1"

# SSH 命令
ssh_cmd = f"""mkdir -p ~/.ssh && echo '{pub_key}' >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys && echo 'SSH key setup done'"""

print(f"Connecting to {MAC_USER}@{MAC_HOST}...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(
        MAC_HOST,
        username=MAC_USER,
        password=MAC_PASS,
        timeout=10,
        allow_agent=False
    )
    print("Connected!")
    
    # 執行命令
    stdin, stdout, stderr = ssh.exec_command(ssh_cmd)
    exit_code = stdout.channel.recv_exit_status()
    
    if exit_code == 0:
        print(f"Success: {stdout.read().decode().strip()}")
    else:
        print(f"Error (exit {exit_code}): {stderr.read().decode().strip()}")
    
    ssh.close()
except paramiko.SSHException as e:
    print(f"SSH Error: {e}")
    sys.exit(1)
