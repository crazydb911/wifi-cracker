import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Install python-multipart
stdin, stdout, stderr = client.exec_command('pip3 install python-multipart')
print('pip3 install python-multipart:')
print(stdout.read().decode())
print(stderr.read().decode())

# Test import again
stdin, stdout, stderr = client.exec_command('cd /Users/crazydb911 && python3 -c "import wifi_cracker; print(\'Import OK\')"')
print("Import test:", stdout.read().decode().strip())
print("Import stderr:", stderr.read().decode().strip())

# Start the server in background
stdin, stdout, stderr = client.exec_command('cd /Users/crazydb911 && nohup python3 wifi_cracker.py > wifi_cracker.log 2>&1 & echo $!')
pid = stdout.read().decode().strip()
print(f"Server started, PID: {pid}")

# Wait a moment then check
import time
time.sleep(3)
stdin, stdout, stderr = client.exec_command('curl -s http://localhost:8765/api/state')
print("State:", stdout.read().decode().strip()[:200])

client.close()
print("Done!")
