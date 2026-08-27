import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check airodump-ng help
print("=== airodump-ng --help ===")
stdin, stdout, stderr = client.exec_command(
    '/usr/local/Cellar/aircrack-ng/1.7_2/sbin/airodump-ng --help 2>&1 | head -50'
)
print(stdout.read().decode())

client.close()
