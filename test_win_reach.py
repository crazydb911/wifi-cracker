"""Test if Mac can reach Windows (192.168.1.107:8766)."""
import paramiko

key = paramiko.Ed25519Key.from_private_key_file(r'C:\Users\crazydb911\.ssh\opremote_ed25519')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', port=22, username='crazydb911', pkey=key, timeout=10)

print("Testing Windows reachability from Mac...")
stdin, stdout, stderr = client.exec_command("python3 -c \"import socket; s=socket.socket(); s.settimeout(3); r=s.connect_ex(('192.168.1.107',8766)); s.close(); print('Windows 8766:', 'OPEN' if r==0 else f'CLOSED ({r})')\"", timeout=10)
print(stdout.read().decode().strip())

# Also check if Windows is on a different IP (Ethernet)
stdin, stdout, stderr = client.exec_command("ifconfig | grep 'inet ' | grep -v 127.0.0.1", timeout=10)
print(f"\nMac IPs:\n{stdout.read().decode()}")

client.close()
