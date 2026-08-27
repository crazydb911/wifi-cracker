import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check aircrack-ng Homebrew info
print("=== aircrack-ng Homebrew info ===")
stdin, stdout, stderr = client.exec_command('/usr/local/bin/brew info aircrack-ng 2>&1')
print(stdout.read().decode())

# Check if there's a specific Mac aircrack-ng package
print("\n=== Homebrew search aircrack ===")
stdin, stdout, stderr = client.exec_command('/usr/local/bin/brew search aircrack 2>&1')
print(stdout.read().decode())

client.close()
