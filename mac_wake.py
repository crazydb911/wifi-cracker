import subprocess
import time
import struct
import socket

MAC = "60:F8:1D:AD:01:E4"
IP = "192.168.1.102"

# Method 1: Wake-on-LAN (magic packet)
print("=== Method 1: Wake-on-LAN ===")
try:
    # Create magic packet: 6 bytes 0xFF + 16x MAC
    mac_bytes = bytes.fromhex(MAC.replace(':', ''))
    magic_packet = b'\xff' * 6 + mac_bytes * 16
    
    # Send to broadcast (192.168.1.255) and local subnet
    for target in ['192.168.1.255', '192.168.1.102']:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, (target, 9))
        sock.close()
        print(f"Sent magic packet to {target}")
    
    # Also try port 7
    for target in ['192.168.1.255', '192.168.1.102']:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, (target, 7))
        sock.close()
        print(f"Sent magic packet to {target}:7")
    
    time.sleep(5)
    
    # Test ping
    result = subprocess.run(['ping', '-n', '1', '-w', '3000', IP], 
                          capture_output=True, text=True, timeout=5)
    if 'TTL' in result.stdout:
        print("SUCCESS: Mac is awake!")
    else:
        print("Mac still sleeping...")
        
except Exception as e:
    print(f"WoL error: {e}")

# Method 2: Ping (keep trying)
print("\n=== Method 2: Ping (30x) ===")
success = False
for i in range(30):
    result = subprocess.run(['ping', '-n', '1', '-w', '2000', IP], 
                          capture_output=True, text=True, timeout=4)
    if 'TTL' in result.stdout:
        print(f"SUCCESS at attempt {i+1}!")
        success = True
        break
    else:
        if i % 5 == 0:
            print(f"Attempt {i+1}: timeout")
        time.sleep(1)

if not success:
    print("All 30 pings failed (60s total)")

# Method 3: SSH (try again)
print("\n=== Method 3: SSH ===")
try:
    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(IP, username='crazydb911', 
                   key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)
    print("SSH connected!")
    
    # Check WiFi status
    stdin, stdout, stderr = client.exec_command('networksetup -getairportpower en0 2>&1')
    wifi = stdout.read().decode().strip()
    print(f"WiFi: {wifi}")
    
    # Check if capture exists
    stdin, stdout, stderr = client.exec_command('ls -la /tmp/all_frames.pcap 2>&1')
    capture = stdout.read().decode().strip()
    print(f"Capture: {capture}")
    
    client.close()
except Exception as e:
    print(f"SSH failed: {e}")
