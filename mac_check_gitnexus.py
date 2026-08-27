"""Check GitNexus for Mac IP."""
import paramiko, socket

# GitNexus is at 192.168.1.115 (NAS)
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

# Check GitNexus (maybe it's running on NAS)
out, _ = ssh("ps aux | grep -i gitnexus | grep -v grep")
print(f"GitNexus process: {out.strip()}")

# Check if GitNexus has API
out, _ = ssh("curl -s http://localhost:3000/api/status 2>&1 | head -5")
print(f"\nGitNexus API: {out.strip()}")

# Check ARP table (maybe Mac is there)
out, _ = ssh("arp -a 2>/dev/null | head -20")
print(f"\nARP table:\n{out}")

# Check DHCP leases
out, _ = ssh("cat /var/lib/dhcpcd/dhcpcd-leases 2>/dev/null | head -20")
print(f"\nDHCP leases:\n{out}")

client.close()
