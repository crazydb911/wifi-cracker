import paramiko
import os

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

sftp = client.open_sftp()

# Upload the cracker
local_path = 'C:/Users/crazydb911/Documents/deepseek/mac_wifi_cracker.py'
remote_path = '/Users/crazydb911/wifi_cracker.py'
sftp.put(local_path, remote_path)
print(f"Uploaded: {local_path} -> {remote_path}")

# Make executable
sftp.chmod(remote_path, 0o755)
print("Made executable")

# Create a start script
start_script = '''#!/bin/bash
cd /Users/crazydb911
python3 wifi_cracker.py
'''
sftp.putfo(start_script.encode(), '/Users/crazydb911/start_cracker.sh')
sftp.chmod('/Users/crazydb911/start_cracker.sh', 0o755)
print("Created start script")

# Upload wordlist (if exists)
rockyou_local = 'C:/wifi-crack/wordlists/rockyou.txt'
rockyou_remote = '/Users/crazydb911/rockyou.txt'
if os.path.exists(rockyou_local):
    sftp.put(rockyou_local, rockyou_remote)
    print(f"Uploaded wordlist: {rockyou_local} -> {rockyou_remote}")

sftp.close()

# Test run
stdin, stdout, stderr = client.exec_command('cd /Users/crazydb911 && python3 -c "import wifi_cracker; print(\'Import OK\')"')
print("Import test:", stdout.read().decode().strip())
print("Import stderr:", stderr.read().decode().strip())

client.close()
print("Done!")
