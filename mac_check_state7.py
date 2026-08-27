"""Check Mac state (retry with WoL)."""
import socket, time, paramiko

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"

# Wait for Mac
print("Waiting for Mac...")
for i in range(30):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    r = s.connect_ex((HOST, 22))
    s.close()
    if r == 0:
        print(f"Mac back after {(i+1)*3}s!")
        break
    time.sleep(3)
else:
    print("Mac still offline, sending WoL...")
    mac = bytes.fromhex('60F81DAD01E4')
    payload = b'\xff' * 6 + mac * 16
    for i in range(30):
        for ip in ['192.168.1.255', HOST]:
            for port in [7, 9]:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.sendto(payload, (ip, port))
                s.close()
        time.sleep(1)
    # Wait again
    for i in range(30):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        r = s.connect_ex((HOST, 22))
        s.close()
        if r == 0:
            print(f"Mac back after WoL + {(i+1)*3}s!")
            break
        time.sleep(3)
    else:
        print("Mac still offline")
        exit()

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)

def ssh_cmd(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Check current state
out, _ = ssh_cmd("networksetup -getairportnetwork en0 2>&1")
print(f"\nWiFi: {out.strip()}")
out, _ = ssh_cmd("ifconfig en0 | grep -E 'status|inet '")
print(f"Interface: {out.strip()}")

client.close()
