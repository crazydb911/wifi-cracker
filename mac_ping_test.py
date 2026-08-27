import paramiko
import time
import subprocess

# Try pinging Mac to wake it up
print("=== Pinging Mac (10x) ===")
for i in range(10):
    result = subprocess.run(['ping', '-n', '1', '192.168.1.102'], 
                          capture_output=True, text=True, timeout=5)
    if 'TTL' in result.stdout:
        print(f"Ping {i+1}: SUCCESS")
        break
    else:
        print(f"Ping {i+1}: timeout")
        time.sleep(1)

# Try SSH
print("\n=== Trying SSH ===")
try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect('192.168.1.102', username='crazydb911', 
                   key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)
    print("SSH connected!")
    
    # Check WiFi status
    stdin, stdout, stderr = client.exec_command('networksetup -getairportpower en0 2>&1')
    print(f"WiFi: {stdout.read().decode().strip()}")
    
    # Check if tshark capture exists
    stdin, stdout, stderr = client.exec_command('ls -la /tmp/all_frames.pcap 2>&1')
    print(f"Capture: {stdout.read().decode().strip()}")
    
    client.close()
except Exception as e:
    print(f"SSH failed: {e}")
