import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check if user can use airodump-ng without sudo
print("=== airodump-ng -i en0 (no sudo) ===")
stdin, stdout, stderr = client.exec_command(
    '/usr/local/Cellar/aircrack-ng/1.7_2/sbin/airodump-ng -i en0 2>&1 | head -20',
    timeout=15
)
print("STDOUT:")
print(stdout.read().decode())
print("STDERR:")
print(stderr.read().decode())

# Check groups
print("\n=== User groups ===")
stdin, stdout, stderr = client.exec_command('groups')
print(stdout.read().decode())

# Check if user is in admin group
print("\n=== dscl ===")
stdin, stdout, stderr = client.exec_command('dscl . -read /Groups/admin GroupMembership 2>&1')
print(stdout.read().decode())

# Try with sudo -n (non-interactive)
print("\n=== airodump-ng with sudo -n ===")
stdin, stdout, stderr = client.exec_command(
    'sudo -n /usr/local/Cellar/aircrack-ng/1.7_2/sbin/airodump-ng -i en0 2>&1 | head -20',
    timeout=15
)
print("STDOUT:")
print(stdout.read().decode())
print("STDERR:")
print(stderr.read().decode())

client.close()
