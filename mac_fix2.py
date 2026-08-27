import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Install python-multipart with timeout
stdin, stdout, stderr = client.exec_command('pip3 install python-multipart', timeout=60)
print('pip3 install python-multipart:')
print(stdout.read().decode())
print(stderr.read().decode())

# Test import again
stdin, stdout, stderr = client.exec_command('cd /Users/crazydb911 && python3 -c "import wifi_cracker; print(\'Import OK\')"')
print("Import test:", stdout.read().decode().strip())
print("Import stderr:", stderr.read().decode().strip())

client.close()
print("Done!")
