import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Find airodump-ng
stdin, stdout, stderr = client.exec_command('find /usr/local/Cellar/aircrack-ng -name "airodump-ng" 2>/dev/null')
out = stdout.read().decode().strip()
print("airodump-ng location:")
print(out)

# Also check for other aircrack tools
stdin, stdout, stderr = client.exec_command('ls /usr/local/Cellar/aircrack-ng/*/bin/ 2>/dev/null')
print("\naircrack-ng bin:")
print(stdout.read().decode().strip())

client.close()
