import paramiko
import time
import json

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Trigger scan
stdin, stdout, stderr = client.exec_command('curl -s -X POST http://localhost:8765/api/scan')
print("Scan triggered:", stdout.read().decode().strip())

# Wait for scan to complete
time.sleep(15)

# Get state
stdin, stdout, stderr = client.exec_command('curl -s http://localhost:8765/api/state')
state = json.loads(stdout.read().decode())
print(f"Status: {state['status']}")
print(f"Message: {state['message']}")
print(f"AP count: {len(state['ap_list'])}")
print("\nNetworks:")
for ap in state['ap_list']:
    print(f"  {ap['ssid']} | {ap['bssid']} | ch{ap['channel']} | {ap['security']} | RSSI {ap['rssi']}")

client.close()
