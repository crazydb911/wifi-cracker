import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

sftp = client.open_sftp()

# Stop the old server
stdin, stdout, stderr = client.exec_command('pkill -f wifi_cracker.py || true')
time.sleep(2)

# Upload the new version
local_path = 'C:/Users/crazydb911/Documents/deepseek/mac_update_cracker.py'
remote_path = '/Users/crazydb911/wifi_cracker.py'
sftp.put(local_path, remote_path)
print(f"Uploaded: {local_path} -> {remote_path}")

sftp.chmod(remote_path, 0o755)
sftp.close()

# Start the new server
stdin, stdout, stderr = client.exec_command('cd /Users/crazydb911 && nohup python3 wifi_cracker.py > wifi_cracker.log 2>&1 & echo $!')
pid = stdout.read().decode().strip()
print(f"Server started, PID: {pid}")

time.sleep(3)
stdin, stdout, stderr = client.exec_command('curl -s http://localhost:8765/api/state')
print("State:", stdout.read().decode().strip()[:200])

client.close()
print("Done!")
