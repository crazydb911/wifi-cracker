"""Check ARP table for Mac MAC (60:F8:1D:AD:01:E4)."""
import paramiko

HOST = "192.168.1.115"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)

def ssh(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Check full ARP table
out, _ = ssh("arp -a 2>/dev/null")
print(f"ARP table:\n{out}")

# Search for Mac MAC (60:F8:1D:AD:01:E4)
out, _ = ssh("arp -a 2>/dev/null | grep -i '60:f8:1d:ad:01:e4'")
print(f"\nMac MAC in ARP: {out.strip()}")

# Also check for 32H9F_5G BSSID (6c:4f:89:4c:a0:e4)
out, _ = ssh("arp -a 2>/dev/null | grep -i '6c:4f:89:4c:a0:e4'")
print(f"\n32H9F_5G BSSID in ARP: {out.strip()}")

client.close()
