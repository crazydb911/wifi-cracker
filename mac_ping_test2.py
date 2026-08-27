import paramiko
import time
import subprocess

# Try pinging Mac with longer timeout
print("=== Pinging Mac (20x, 5s each) ===")
success = False
for i in range(20):
    result = subprocess.run(['ping', '-n', '1', '-w', '5000', '192.168.1.102'], 
                          capture_output=True, text=True, timeout=10)
    if 'TTL' in result.stdout:
        print(f"Ping {i+1}: SUCCESS at {i*5}s")
        success = True
        break
    else:
        if i % 5 == 0:
            print(f"Ping {i+1}: timeout")
        time.sleep(0.5)

if not success:
    print("All 20 pings failed (100s total)")
    print("Mac is likely in sleep or WiFi still off")
    print("\nOptions:")
    print("1. Wake Mac (open lid or press key)")
    print("2. Enable Wake-on-LAN (if not already)")
    print("3. Wait for Mac to auto-wake")
