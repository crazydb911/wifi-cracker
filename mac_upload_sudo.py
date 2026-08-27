"""Upload sudo_cap.pcap to Windows for extraction."""
import paramiko, requests, time

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "

# Get the pcap from Mac
key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)

sftp = client.open_sftp()
remote_path = "/Users/crazydb911/sudo_cap.pcap"
local_path = r"C:\Users\crazydb911\Documents\deepseek\sudo_cap.pcap"

print(f"Downloading {remote_path}...")
sftp.get(remote_path, local_path)
size = __import__('os').path.getsize(local_path)
print(f"Downloaded: {size//1024}KB")
sftp.close()
client.close()

# Upload to Windows
print(f"\nUploading to Windows (192.168.1.107:8766)...")
with open(local_path, 'rb') as f:
    r = requests.post(
        'http://192.168.1.107:8766/api/extract',
        files={'file': ('sudo_cap.pcap', f, 'application/octet-stream')},
        data={'ssid': '32H9F_5G'},
        timeout=30
    )
print(f"Upload: {r.json()}")

# Wait for extraction
time.sleep(5)
r = requests.get('http://192.168.1.107:8766/api/state', timeout=5)
d = r.json()
print(f"\nStatus: {d['status']}")
print(f"Message: {d['message']}")
print(f"Hash count: {d['hash_count']}")
print(f"Hash file: {d['hash_file']}")
if d['results']:
    print(f"Results: {d['results']}")
print(f"Nonce issues: {d.get('nonce_issues', 'N/A')}")
