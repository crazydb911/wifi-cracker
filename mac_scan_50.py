import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Copy test8.pcap to home dir and check
print("=== Copy test8.pcap and check ===")
shell = client.invoke_shell()
time.sleep(2)
shell.send("sudo -S cp /tmp/test8.pcap ~/test8.pcap 2>&1\n")
time.sleep(2)
shell.send(" \n")
time.sleep(2)
shell.send("sudo -S chmod 644 ~/test8.pcap 2>&1\n")
time.sleep(2)
shell.send(" \n")
time.sleep(2)
shell.send("tshark -r ~/test8.pcap -c 10 2>&1\n")
time.sleep(3)

output = ""
while shell.recv_ready():
    output += shell.recv(65535).decode()
while shell.recv_stderr_ready():
    output += shell.recv_stderr(65535).decode()

print(f"Output ({len(output)} chars):")
print(output[:3000])

client.close()
