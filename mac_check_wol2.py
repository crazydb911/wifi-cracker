"""Check Mac with WoL (fast)."""
import socket

HOST = "192.168.1.102"
mac = bytes.fromhex('60F81DAD01E4')
payload = b'\xff' * 6 + mac * 16

# Send WoL
print("Sending WoL...")
for i in range(10):
    for ip in ['192.168.1.255', HOST]:
        for port in [7, 9]:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(payload, (ip, port))
            s.close()

# Wait 10s
import time
time.sleep(10)

# Check ports
for port in [22, 8765]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        r = s.connect_ex((HOST, port))
        print(f"Port {port}: {'OPEN' if r == 0 else f'CLOSED'}")
    finally:
        s.close()
