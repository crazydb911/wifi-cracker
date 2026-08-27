import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Try with sudo -S (read password from stdin)
print("=== airodump-ng with sudo -S ===")
stdin, stdout, stderr = client.exec_command(
    'echo "crazydb911" | sudo -S /usr/local/Cellar/aircrack-ng/1.7_2/sbin/airodump-ng -i en0 2>&1 | head -30',
    timeout=20
)
print("STDOUT:")
print(stdout.read().decode())
print("STDERR:")
print(stderr.read().decode())

# Try airport with sudo
print("\n=== airport -s with sudo ===")
airport = '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport'
stdin, stdout, stderr = client.exec_command(
    f'echo "crazydb911" | sudo -S {airport} -s 2>&1 | head -20',
    timeout=20
)
print("STDOUT:")
print(stdout.read().decode())
print("STDERR:")
print(stderr.read().decode())

client.close()
