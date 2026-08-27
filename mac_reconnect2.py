import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check if capture file exists
print("=== Check capture file ===")
stdin, stdout, stderr = client.exec_command('ls -la /tmp/eapol_capture.pcap 2>&1')
print(stdout.read().decode())

# Check if tshark is still running
print("\n=== Check tshark ===")
stdin, stdout, stderr = client.exec_command('ps aux | grep tshark | grep -v grep 2>&1')
print(stdout.read().decode())

# Check WiFi status
print("\n=== WiFi status ===")
stdin, stdout, stderr = client.exec_command('networksetup -getairportpower en0 2>&1')
print(stdout.read().decode())

client.close()
