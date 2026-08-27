import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check Mac cracker state
stdin, stdout, stderr = client.exec_command('curl -s http://localhost:8765/api/state', timeout=10)
import json
state = json.loads(stdout.read().decode())
print(f"Mac Cracker: {state['status']} - {state['message']}")
print(f"AP count: {len(state['ap_list'])}")

# Check Mac log
stdin, stdout, stderr = client.exec_command('tail -10 /Users/crazydb911/wifi_cracker.log')
print("\nMac log:")
print(stdout.read().decode())

client.close()
