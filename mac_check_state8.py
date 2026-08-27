"""Check Mac state (simple, no timeout)."""
import socket

HOST = "192.168.1.102"
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
try:
    r = s.connect_ex((HOST, 22))
    print(f"Mac SSH: {'OPEN' if r == 0 else f'CLOSED ({r})'}")
finally:
    s.close()
