import subprocess
import time
import socket

IP = "192.168.1.102"

# Method 1: Send more WoL packets (aggressive)
print("=== Method 1: Aggressive WoL (50 packets) ===")
mac_bytes = bytes.fromhex("60F81DAD01E4")
magic_packet = b'\xff' * 6 + mac_bytes * 16

for i in range(50):
    for target in ['192.168.1.255', '192.168.1.102', '255.255.255.255']:
        for port in [9, 7, 40000, 40001]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.sendto(magic_packet, (target, port))
                sock.close()
            except:
                pass
    if i % 10 == 0:
        print(f"Sent {i*4} packets...")
    time.sleep(0.5)

print(f"Sent {50*4} WoL packets")

# Method 2: Ping (100x, 1s each)
print("\n=== Method 2: Ping (100x, 1s each) ===")
success = False
for i in range(100):
    result = subprocess.run(['ping', '-n', '1', '-w', '1000', IP], 
                          capture_output=True, text=True, timeout=2)
    if 'TTL' in result.stdout:
        print(f"SUCCESS at attempt {i+1}!")
        success = True
        break
    else:
        if i % 20 == 0:
            print(f"Attempt {i+1}: timeout")
        time.sleep(0.5)

if not success:
    print("All 100 pings failed (100s total)")
    print("\nMac is likely:")
    print("1. In sleep (lid closed)")
    print("2. WiFi still off")
    print("3. Power off")
    print("\nTry: Open Mac lid or press any key")

# Method 3: SSH (final try)
print("\n=== Method 3: SSH ===")
try:
    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(IP, username='crazydb911', 
                   key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)
    print("SSH connected!")
    
    stdin, stdout, stderr = client.exec_command('networksetup -getairportpower en0 2>&1')
    wifi = stdout.read().decode().strip()
    print(f"WiFi: {wifi}")
    
    stdin, stdout, stderr = client.exec_command('ls -la /tmp/all_frames.pcap 2>&1')
    capture = stdout.read().decode().strip()
    print(f"Capture: {capture}")
    
    client.close()
except Exception as e:
    print(f"SSH failed: {e}")
