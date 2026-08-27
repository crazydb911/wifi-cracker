"""Check Mac HTTP + SSH."""
import requests, socket

HOST = "192.168.1.102"

# Check HTTP
print("Checking Mac HTTP (8765)...")
try:
    r = requests.get(f'http://{HOST}:8765/api/state', timeout=5)
    print(f"HTTP: {r.status_code} - {r.json().get('status', 'unknown')}")
except Exception as e:
    print(f"HTTP: {e}")

# Check SSH
print("\nChecking Mac SSH (22)...")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    r = s.connect_ex((HOST, 22))
    print(f"SSH: {'OPEN' if r == 0 else f'CLOSED ({r})'}")
finally:
    s.close()
