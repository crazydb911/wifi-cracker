"""Check SSH port."""
import socket

HOST = "192.168.1.102"
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    r = s.connect_ex((HOST, 22))
    print(f"Mac SSH (22): {'OPEN' if r == 0 else f'CLOSED ({r})'}")
finally:
    s.close()

# Check Mac app port
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    r = s.connect_ex((HOST, 8765))
    print(f"Mac app (8765): {'OPEN' if r == 0 else f'CLOSED ({r})'}")
finally:
    s.close()
