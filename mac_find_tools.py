import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check common locations
tools = [
    '/usr/local/bin/airport',
    '/usr/local/bin/hcxdumptool',
    '/usr/local/bin/airodump-ng',
    '/usr/local/bin/tshark',
    '/usr/local/bin/hcxpcapngtool',
    '/usr/local/bin/hashcat',
    '/opt/homebrew/bin/airport',
    '/opt/homebrew/bin/hcxdumptool',
    '/opt/homebrew/bin/airodump-ng',
    '/opt/homebrew/bin/tshark',
    '/opt/homebrew/bin/hcxpcapngtool',
    '/opt/homebrew/bin/hashcat',
]

for tool in tools:
    stdin, stdout, stderr = client.exec_command(f'ls -la {tool} 2>/dev/null || echo "NOT FOUND"')
    out = stdout.read().decode().strip()
    if 'NOT FOUND' not in out:
        print(f"FOUND: {tool}")
        print(f"  {out}")

# Also check if brew is installed
stdin, stdout, stderr = client.exec_command('which brew || echo "NOT FOUND"')
print("\nbrew:", stdout.read().decode().strip())

# Check if aircrack-ng package is installed
stdin, stdout, stderr = client.exec_command('brew list aircrack-ng 2>/dev/null | head -20 || echo "NOT INSTALLED"')
print("\naircrack-ng:", stdout.read().decode().strip())

client.close()
