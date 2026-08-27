import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check for EAPOL frames in all_frames.pcap
print("=== Check for EAPOL frames ===")
stdin, stdout, stderr = client.exec_command('tshark -r ~/all_frames.pcap -Y eapol 2>&1 | head -20')
print(stdout.read().decode())

# Check for 32H9F_5G frames
print("\n=== Check for 32H9F_5G frames ===")
stdin, stdout, stderr = client.exec_command('tshark -r ~/all_frames.pcap -Y "wlan.sa == 4c:a0:e4" 2>&1 | head -20')
print(stdout.read().decode())

client.close()
