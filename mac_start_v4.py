import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Use a start script instead of nohup
start_script = '''#!/bin/bash
cd /Users/crazydb911
nohup python3 wifi_cracker.py > wifi_cracker.log 2>&1 &
echo $!
'''

sftp = client.open_sftp()
with sftp.open('/Users/crazydb911/start_cracker.sh', 'w') as f:
    f.write(start_script)
sftp.chmod('/Users/crazydb911/start_cracker.sh', 0o755)
sftp.close()

# Run the start script
stdin, stdout, stderr = client.exec_command('/Users/crazydb911/start_cracker.sh', timeout=10)
pid = stdout.read().decode().strip()
print(f"Server started, PID: {pid}")

time.sleep(5)

# Check state
stdin, stdout, stderr = client.exec_command('curl -s http://localhost:8765/api/state', timeout=10)
print("State:", stdout.read().decode().strip()[:200])

client.close()
print("Done!")
