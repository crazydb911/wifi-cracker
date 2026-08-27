import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check aircrack-ng logs
print("=== aircrack-ng logs ===")
stdin, stdout, stderr = client.exec_command('log show --predicate "subsystem == \"org.aircrack-ng\"" --last 5m 2>&1 | tail -20')
print(stdout.read().decode())

# Try with strace (if available)
print("\n=== airodump-ng with strace ===")
shell = client.invoke_shell()
time.sleep(2)
shell.send("sudo -S strace /usr/local/Cellar/aircrack-ng/1.7_2/sbin/airodump-ng en0 2>&1 | head -50\n")
time.sleep(3)
shell.send(" \n")  # Space
time.sleep(10)

output = ""
while shell.recv_ready():
    output += shell.recv(65535).decode()
while shell.recv_stderr_ready():
    output += shell.recv_stderr(65535).decode()

print(f"Output ({len(output)} chars):")
print(output[:3000])

client.close()
