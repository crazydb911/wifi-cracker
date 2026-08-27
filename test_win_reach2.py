"""Test Windows reachability - check if Windows is listening on all interfaces."""
import paramiko

key = paramiko.Ed25519Key.from_private_key_file(r'C:\Users\crazydb911\.ssh\opremote_ed25519')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', port=22, username='crazydb911', pkey=key, timeout=10)

print("Testing Windows reachability...")
for ip in ['192.168.1.107', '192.168.1.102']:
    stdin, stdout, stderr = client.exec_command(
        f"python3 -c \"import socket; s=socket.socket(); s.settimeout(3); r=s.connect_ex(('{ip}',8766)); s.close(); print('{ip}:', 'OPEN' if r==0 else f'CLOSED ({r})')\"", 
        timeout=10)
    print(stdout.read().decode().strip())

# Check Windows IP from Mac's perspective
print("\nTraceroute to 192.168.1.107:")
stdin, stdout, stderr = client.exec_command("traceroute -m 3 192.168.1.107 2>&1", timeout=15)
print(stdout.read().decode())

client.close()
