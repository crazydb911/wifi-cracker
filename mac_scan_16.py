import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Try airport -s (no sudo needed)
print("=== airport -s ===")
airport = '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport'
stdin, stdout, stderr = client.exec_command(f'{airport} -s 2>&1', timeout=20)
out = stdout.read().decode()
err = stderr.read().decode()
print(f"STDOUT ({len(out)} chars):")
print(out[:3000])
print(f"STDERR ({len(err)} chars):")
print(err[:500])

client.close()
