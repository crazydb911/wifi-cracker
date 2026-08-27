import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check if Mac has hashcat
stdin, stdout, stderr = client.exec_command('which hashcat || ls /usr/local/bin/hashcat 2>/dev/null || echo "NOT FOUND"')
print("Mac hashcat:", stdout.read().decode().strip())

# Check Mac GPU
stdin, stdout, stderr = client.exec_command('system_profiler SPDisplaysDataType 2>/dev/null | head -20')
print("\nMac GPU:")
print(stdout.read().decode())

client.close()
