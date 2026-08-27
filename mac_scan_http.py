"""Scan 192.168.1.x for Mac app (port 8765)."""
import socket

print("Scanning 192.168.1.x for Mac app (port 8765)...")
found = []
for ip in range(1, 254):
    host = f"192.168.1.{ip}"
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        r = s.connect_ex((host, 8765))
        if r == 0:
            print(f"  {host}: Port 8765 OPEN")
            found.append(host)
    except:
        pass
    finally:
        s.close()

print(f"\nFound {len(found)} hosts with port 8765 open")
