"""Scan 192.168.1.x for Mac (SSH port 22)."""
import socket, time

print("Scanning 192.168.1.x for SSH (port 22)...")
found = []
for ip in range(1, 254):
    host = f"192.168.1.{ip}"
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        r = s.connect_ex((host, 22))
        if r == 0:
            print(f"  {host}: SSH OPEN")
            found.append(host)
    except:
        pass
    finally:
        s.close()

print(f"\nFound {len(found)} hosts with SSH open")
