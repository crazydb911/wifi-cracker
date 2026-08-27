"""Test Windows reachability - simpler."""
import paramiko, time

key = paramiko.Ed25519Key.from_private_key_file(r'C:\Users\crazydb911\.ssh\opremote_ed25519')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', port=22, username='crazydb911', pkey=key, timeout=10)

# Write test script to Mac
sftp = client.open_sftp()
with sftp.open('/tmp/test_win.py', 'w') as f:
    f.write("""import socket
for ip in ['192.168.1.107', '192.168.1.102']:
    s = socket.socket()
    s.settimeout(5)
    r = s.connect_ex((ip, 8766))
    s.close()
    status = 'OPEN' if r == 0 else f'CLOSED ({r})'
    print(f'{ip}: {status}')
""")
sftp.close()

# Run it
print("Testing Windows reachability from Mac...")
stdin, stdout, stderr = client.exec_command("python3 /tmp/test_win.py", timeout=15)
print(stdout.read().decode())

client.close()
