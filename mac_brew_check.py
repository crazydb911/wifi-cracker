import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check for Homebrew in common locations
locations = [
    '/usr/local/bin/brew',
    '/opt/homebrew/bin/brew',
    '/home/linuxbrew/.linuxbrew/bin/brew',
]

for loc in locations:
    stdin, stdout, stderr = client.exec_command(f'ls -la {loc} 2>/dev/null || echo "NOT FOUND"')
    out = stdout.read().decode().strip()
    if 'NOT FOUND' not in out:
        print(f"FOUND: {loc}")

# Check Cellar for aircrack-ng
stdin, stdout, stderr = client.exec_command('ls /usr/local/Cellar/ 2>/dev/null | grep -i aircrack || echo "NOT FOUND"')
print("\naircrack in Cellar:", stdout.read().decode().strip())

# Check Cellar for hcxdumptool
stdin, stdout, stderr = client.exec_command('ls /usr/local/Cellar/ 2>/dev/null | grep -i hcx || echo "NOT FOUND"')
print("hcx in Cellar:", stdout.read().decode().strip())

# List all Cellar packages
stdin, stdout, stderr = client.exec_command('ls /usr/local/Cellar/ 2>/dev/null')
packages = stdout.read().decode().strip()
print("\nAll Cellar packages:")
print(packages)

client.close()
