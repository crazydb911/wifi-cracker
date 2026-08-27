"""Check Mac IP (maybe it changed)."""
import subprocess, time

# Ping 192.168.1.102
print("Pinging 192.168.1.102...")
r = subprocess.run(['ping', '-n', '2', '192.168.1.102'], capture_output=True, text=True, timeout=10)
print(r.stdout[:300])

# Maybe Mac got a different IP? Try scanning
print("\nScanning for Mac (192.168.1.x)...")
import socket
for ip in range(100, 110):
    host = f"192.168.1.{ip}"
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        r = s.connect_ex((host, 22))
        if r == 0:
            print(f"  {host}: SSH OPEN")
    except:
        pass
    finally:
        s.close()
