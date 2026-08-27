import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check if aircrack-ng supports Apple WiFi
print("=== aircrack-ng version ===")
stdin, stdout, stderr = client.exec_command('/usr/local/Cellar/aircrack-ng/1.7_2/sbin/airodump-ng --version 2>&1')
print(stdout.read().decode())

# Check if there's a monitor mode interface
print("\n=== ifconfig (all interfaces) ===")
stdin, stdout, stderr = client.exec_command('ifconfig 2>&1 | grep -E "^[a-z]|BPF|PROMISC" | head -20')
print(stdout.read().decode())

# Try creating a monitor interface
print("\n=== Create monitor interface ===")
shell = client.invoke_shell()
time.sleep(2)
shell.send("sudo -S ifconfig en0 create 2>&1\n")
time.sleep(2)
shell.send(" \n")
time.sleep(3)
shell.send("sudo -S ifconfig en1 create 2>&1\n")
time.sleep(2)
shell.send(" \n")
time.sleep(3)
shell.send("ifconfig 2>&1 | grep -E '^[a-z]|BPF|PROMISC' | head -20\n")
time.sleep(2)

output = ""
while shell.recv_ready():
    output += shell.recv(65535).decode()
while shell.recv_stderr_ready():
    output += shell.recv_stderr(65535).decode()

print(f"Output ({len(output)} chars):")
print(output[:3000])

client.close()
