"""Check Mac ports (fast)."""
import socket

HOST = "192.168.1.102"

for port in [22, 8765]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        r = s.connect_ex((HOST, port))
        print(f"Port {port}: {'OPEN' if r == 0 else f'CLOSED'}")
    finally:
        s.close()
