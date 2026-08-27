"""Check Mac firewall + send WoL."""
import subprocess, time, socket

HOST = "192.168.1.102"

# Ping first
print("Pinging Mac...")
r = subprocess.run(['ping', '-n', '2', HOST], capture_output=True, text=True, timeout=10)
print(r.stdout[:300])

# Send WoL
print("\nSending WoL...")
mac = bytes.fromhex('60F81DAD01E4')
payload = b'\xff' * 6 + mac * 16
for i in range(30):
    for ip in ['192.168.1.255', HOST]:
        for port in [7, 9]:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(payload, (ip, port))
            s.close()
    time.sleep(1)

# Wait 30s
print("Waiting 30s...")
time.sleep(30)

# Check SSH
print("\nChecking SSH...")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    r = s.connect_ex((HOST, 22))
    print(f"SSH: {'OPEN' if r == 0 else f'CLOSED ({r})'}")
finally:
    s.close()

# Check HTTP
print("\nChecking HTTP...")
import requests
try:
    r = requests.get(f'http://{HOST}:8765/api/state', timeout=5)
    print(f"HTTP: {r.status_code} - {r.json().get('status', 'unknown')}")
except Exception as e:
    print(f"HTTP: {str(e)[:100]}")
