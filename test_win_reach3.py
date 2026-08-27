"""Test Windows reachability."""
import paramiko

key = paramiko.Ed25519Key.from_private_key_file(r'C:\Users\crazydb911\.ssh\opremote_ed25519')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', port=22, username='crazydb911', pkey=key, timeout=10)

print("Testing Windows reachability from Mac...")
# Use a simple script on Mac
test_script = '''
import socket
for ip in ['192.168.1.107', '192.168.1.102']:
    s = socket.socket()
    s.settimeout(3)
    r = s.connect_ex((ip, 8766))
    s.close()
    status = 'OPEN' if r == 0 else f'CLOSED ({r})'
    print(f'{ip}: {status}')
'''
stdin, stdout, stderr = client.exec_command(f"python3 -c '{test_script}'", timeout=15)
print(stdout.read().decode())

client.close()
