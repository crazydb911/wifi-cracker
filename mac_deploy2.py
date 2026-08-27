import paramiko
import os
import io

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

sftp = client.open_sftp()

# Create a start script
start_script = '''#!/bin/bash
cd /Users/crazydb911
python3 wifi_cracker.py
'''
with sftp.open('/Users/crazydb911/start_cracker.sh', 'w') as f:
    f.write(start_script)
sftp.chmod('/Users/crazydb911/start_cracker.sh', 0o755)
print("Created start script")

# Upload wordlist (if exists)
rockyou_local = 'C:/wifi-crack/wordlists/rockyou.txt'
rockyou_remote = '/Users/crazydb911/rockyou.txt'
if os.path.exists(rockyou_local):
    sftp.put(rockyou_local, rockyou_remote)
    print(f"Uploaded wordlist: {rockyou_local} -> {rockyou_remote}")

sftp.close()

# Test import
stdin, stdout, stderr = client.exec_command('cd /Users/crazydb911 && python3 -c "import wifi_cracker; print(\'Import OK\')"')
print("Import test:", stdout.read().decode().strip())
print("Import stderr:", stderr.read().decode().strip())

client.close()
print("Done!")
