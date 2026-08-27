import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Try different passwords
passwords = ["crazydb911", "Crazydb911", "crazydb911!", "Crazydb911!", "crazydb", "Crazydb", "123456", "password"]

for pwd in passwords:
    print(f"\n=== Trying password: {pwd} ===")
    shell = client.invoke_shell()
    time.sleep(2)
    shell.send("sudo -S /usr/local/Cellar/aircrack-ng/1.7_2/sbin/airodump-ng -i en0 2>&1 | head -5\n")
    time.sleep(2)
    shell.send(f"{pwd}\n")
    time.sleep(3)
    
    output = ""
    while shell.recv_ready():
        output += shell.recv(65535).decode()
    while shell.recv_stderr_ready():
        output += shell.recv_stderr(65535).decode()
    
    if "Sorry, try again" not in output and "Password:" not in output[-50:]:
        print(f"SUCCESS! Output:")
        print(output[:500])
        break
    else:
        print(f"Failed (got {len(output)} chars)")
        time.sleep(1)

client.close()
