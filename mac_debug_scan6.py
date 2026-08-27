import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Try with explicit password
print("=== airodump-ng with password ===")
stdin, stdout, stderr = client.exec_command(
    'printf "crazydb911\\n" | sudo -S /usr/local/Cellar/aircrack-ng/1.7_2/sbin/airodump-ng -i en0 2>&1 | head -30',
    timeout=20
)
out = stdout.read().decode()
err = stderr.read().decode()
print(f"STDOUT ({len(out)} chars):")
print(out[:2000])
print(f"STDERR ({len(err)} chars):")
print(err[:500])

# Try with -p flag
print("\n=== airodump-ng with -p flag ===")
stdin, stdout, stderr = client.exec_command(
    'sudo -p "" /usr/local/Cellar/aircrack-ng/1.7_2/sbin/airodump-ng -i en0 2>&1 | head -30',
    timeout=20
)
out = stdout.read().decode()
err = stderr.read().decode()
print(f"STDOUT ({len(out)} chars):")
print(out[:2000])
print(f"STDERR ({len(err)} chars):")
print(err[:500])

client.close()
