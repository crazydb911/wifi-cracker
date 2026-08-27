"""Check Mac ping."""
import subprocess

r = subprocess.run(['ping', '-n', '2', '192.168.1.102'], capture_output=True, text=True, timeout=10)
print(r.stdout[:300])
