import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Try just the first password with longer wait
print("=== Trying crazydb911 ===")
shell = client.invoke_shell()
time.sleep(2)
shell.send("sudo -S /usr/local/Cellar/aircrack-ng/1.7_2/sbin/airodump-ng -i en0 2>&1 | head -5\n")
time.sleep(3)
shell.send("crazydb911\n")
time.sleep(10)

output = ""
while shell.recv_ready():
    output += shell.recv(65535).decode()
while shell.recv_stderr_ready():
    output += shell.recv_stderr(65535).decode()

print(f"Output ({len(output)} chars):")
print(output[:2000])

client.close()
