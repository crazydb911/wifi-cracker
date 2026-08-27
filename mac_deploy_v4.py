import paramiko
import time
import os

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Stop old server
stdin, stdout, stderr = client.exec_command('pkill -f wifi_cracker.py || true', timeout=10)
time.sleep(2)

sftp = client.open_sftp()

# Upload new version
local_path = 'C:/Users/crazydb911/Documents/deepseek/mac_wifi_cracker_v4.py'
remote_path = '/Users/crazydb911/wifi_cracker.py'
sftp.put(local_path, remote_path)
print(f"Uploaded: {local_path} -> {remote_path}")

sftp.chmod(remote_path, 0o755)

# Upload wordlist
local_wl = 'C:/Users/crazydb911/Documents/deepseek/wifi_wordlist_combined.txt'
if not os.path.exists(local_wl):
    local_wl = 'C:/wifi-crack/wordlists/wifi_wordlist_combined.txt'
remote_wl = '/tmp/wifi_wordlist.txt'
sftp.put(local_wl, remote_wl)
print(f"Uploaded wordlist: {local_wl} -> {remote_wl}")

sftp.close()

# Start new server
start_script = '''#!/bin/bash
cd /Users/crazydb911
nohup python3 wifi_cracker.py > wifi_cracker.log 2>&1 &
echo $!
'''
with client.open_sftp().open('/Users/crazydb911/start_cracker.sh', 'w') as f:
    f.write(start_script)
client.exec_command('chmod +x /Users/crazydb911/start_cracker.sh')

stdin, stdout, stderr = client.exec_command('/Users/crazydb911/start_cracker.sh', timeout=10)
pid = stdout.read().decode().strip()
print(f"Server started, PID: {pid}")

time.sleep(5)
stdin, stdout, stderr = client.exec_command('curl -s http://localhost:8765/api/state', timeout=10)
print("State:", stdout.read().decode().strip()[:200])

client.close()
print("Done!")
