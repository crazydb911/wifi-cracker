import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Try wdutil scan
print("=== wdutil scan ===")
stdin, stdout, stderr = client.exec_command('sudo wdutil scan 2>&1 | head -30', timeout=20)
print("STDOUT:")
print(stdout.read().decode())
print("STDERR:")
print(stderr.read().decode())

# Try system_profiler
print("\n=== system_profiler SPAirPortDataType ===")
stdin, stdout, stderr = client.exec_command('system_profiler SPAirPortDataType 2>&1 | head -40', timeout=15)
print(stdout.read().decode())

# Check if en0 is up
print("\n=== ifconfig en0 ===")
stdin, stdout, stderr = client.exec_command('ifconfig en0 2>&1 | head -10')
print(stdout.read().decode())

# Check WiFi status
print("\n=== WiFi status ===")
stdin, stdout, stderr = client.exec_command('networksetup -getairportpower en0 2>&1')
print(stdout.read().decode())

client.close()
