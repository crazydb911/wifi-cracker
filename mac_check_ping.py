"""Check Mac ping + WoL."""
import subprocess, time, socket

HOST = "192.168.1.102"

# Ping Mac
print("Pinging Mac...")
r = subprocess.run(['ping', '-n', '3', HOST], capture_output=True, text=True, timeout=15)
print(r.stdout[:500])

# Check SSH port
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
r = s.connect_ex((HOST, 22))
s.close()
print(f"\nMac SSH: {'OPEN' if r == 0 else f'CLOSED ({r})'}")

# Send WoL
if r != 0:
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
    print("WoL sent, waiting 30s...")
    time.sleep(30)
    
    # Check again
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    r = s.connect_ex((HOST, 22))
    s.close()
    print(f"Mac SSH: {'OPEN' if r == 0 else f'CLOSED ({r})'}")
