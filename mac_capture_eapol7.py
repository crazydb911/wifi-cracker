import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check for EAPOL frames in all_frames.pcap
print("=== Check for EAPOL frames ===")
shell = client.invoke_shell()
time.sleep(2)
shell.send("/usr/local/bin/tshark -r ~/all_frames.pcap -Y eapol 2>&1 | head -20\n")
time.sleep(5)

output = ""
while shell.recv_ready():
    output += shell.recv(65535).decode()
while shell.recv_stderr_ready():
    output += shell.recv_stderr(65535).decode()

print(f"Output ({len(output)} chars):")
print(output[:3000])

# Check for 32H9F_5G frames
print("\n=== Check for 32H9F_5G frames ===")
shell.send("/usr/local/bin/tshark -r ~/all_frames.pcap -Y \"wlan.sa == 4c:a0:e4\" 2>&1 | head -20\n")
time.sleep(5)

output2 = ""
while shell.recv_ready():
    output2 += shell.recv(65535).decode()
while shell.recv_stderr_ready():
    output2 += shell.recv_stderr(65535).decode()

print(f"Output ({len(output2)} chars):")
print(output2[:3000])

client.close()
