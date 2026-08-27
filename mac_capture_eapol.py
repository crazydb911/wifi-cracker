import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Capture EAPOL frames for 32H9F_5G
print("=== tshark capture EAPOL for 32H9F_5G (60s) ===")
shell = client.invoke_shell()
time.sleep(2)
shell.send("sudo -S /usr/local/bin/tshark -i en0 -I -y IEEE802_11 -f 'wlan[0] == 0x8863' -c 50 -w /tmp/32h9f_eapol_new.pcap 2>&1\n")
time.sleep(3)
shell.send(" \n")  # Space
time.sleep(65)

output = ""
while shell.recv_ready():
    output += shell.recv(65535).decode()
while shell.recv_stderr_ready():
    output += shell.recv_stderr(65535).decode()

print(f"Output ({len(output)} chars):")
print(output[:3000])

# Copy to home and check
print("\n=== Copy and check ===")
shell.send("sudo -S cp /tmp/32h9f_eapol_new.pcap ~/32h9f_eapol_new.pcap 2>&1\n")
time.sleep(2)
shell.send(" \n")
time.sleep(2)
shell.send("sudo -S chmod 644 ~/32h9f_eapol_new.pcap 2>&1\n")
time.sleep(2)
shell.send(" \n")
time.sleep(2)
shell.send("tshark -r ~/32h9f_eapol_new.pcap -c 20 2>&1\n")
time.sleep(3)

output2 = ""
while shell.recv_ready():
    output2 += shell.recv(65535).decode()
while shell.recv_stderr_ready():
    output2 += shell.recv_stderr(65535).decode()

print(f"Output ({len(output2)} chars):")
print(output2[:3000])

client.close()
