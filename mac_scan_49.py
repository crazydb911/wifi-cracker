import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check if test8.pcap has 802.11 frames
print("=== tshark -r /tmp/test8.pcap (first 10 frames) ===")
stdin, stdout, stderr = client.exec_command('/usr/local/bin/tshark -r /tmp/test8.pcap -c 10 2>&1')
print(stdout.read().decode())

# Check linktype
print("\n=== tshark -r /tmp/test8.pcap (linktype) ===")
stdin, stdout, stderr = client.exec_command('/usr/local/bin/tshark -r /tmp/test8.pcap -V 2>&1 | head -20')
print(stdout.read().decode())

client.close()
