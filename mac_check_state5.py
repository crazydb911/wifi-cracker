"""Check Mac state (simple)."""
import socket

HOST = "192.168.1.102"
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
r = s.connect_ex((HOST, 22))
s.close()
print(f"Mac SSH: {'OPEN' if r == 0 else f'CLOSED ({r})'}")
