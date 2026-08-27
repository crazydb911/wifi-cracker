import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Test airodump-ng with -i en0
print("=== airodump-ng -i en0 ===")
stdin, stdout, stderr = client.exec_command(
    '/usr/local/Cellar/aircrack-ng/1.7_2/sbin/airodump-ng -i en0 2>&1 | head -40',
    timeout=15
)
print("STDOUT:")
print(stdout.read().decode())
print("STDERR:")
print(stderr.read().decode())

# Test airport -s with full path
print("\n=== airport -s (full) ===")
airport = '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport'
stdin, stdout, stderr = client.exec_command(f'{airport} -s 2>&1', timeout=20)
out = stdout.read().decode()
err = stderr.read().decode()
print(f"STDOUT ({len(out)} chars):")
print(out[:2000])
print(f"STDERR ({len(err)} chars):")
print(err[:500])

client.close()
