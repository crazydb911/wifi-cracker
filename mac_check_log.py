import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check the log
stdin, stdout, stderr = client.exec_command('cat /Users/crazydb911/wifi_cracker.log')
print("Log:")
print(stdout.read().decode())

# Check if the process is running
stdin, stdout, stderr = client.exec_command('ps aux | grep wifi_cracker | grep -v grep')
print("Process:")
print(stdout.read().decode())

# Check if port 8765 is listening
stdin, stdout, stderr = client.exec_command('lsof -i :8765')
print("Port 8765:")
print(stdout.read().decode())

client.close()
