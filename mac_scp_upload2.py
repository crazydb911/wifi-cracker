"""SCP capture files from Mac to Windows (fix host key), then extract."""
import paramiko, time, requests

MAC_HOST = "192.168.1.102"
WIN_HOST = "192.168.1.107"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"

# Capture files on Mac
files = [
    "/Users/crazydb911/cap_f8345a8c1f9f_1787845952.pcap",  # BruceWen-5G
    "/Users/crazydb911/cap_003192338022_1787845902.pcap",  # Han_5G
    "/Users/crazydb911/cap_3c7c3ff6e58c_1787845852.pcap",  # TP-LINK_lucien_5G
    "/Users/crazydb911/cap_a2ad9ff33820_1787845801.pcap",  # Kurt Home
]

# SCP each file from Mac to Windows
key = paramiko.Ed25519Key.from_private_key_file(KEY)
mac_client = paramiko.SSHClient()
mac_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
mac_client.connect(MAC_HOST, port=22, username=USER, pkey=key, timeout=15)

def ssh_mac(cmd, timeout=30):
    stdin, stdout, stderr = mac_client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# First, add Windows to Mac's known_hosts
out, err = ssh_mac(f"ssh-keyscan {WIN_HOST} >> ~/.ssh/known_hosts 2>&1", timeout=15)
print(f"Known hosts: {out.strip() or err.strip()}")

for i, filepath in enumerate(files):
    filename = filepath.split('/')[-1]
    print(f"\n[{i+1}/{len(files)}] {filename}")
    
    # SCP from Mac to Windows
    out, err = ssh_mac(f"scp {filepath} {USER}@{WIN_HOST}:/Users/{USER}/ 2>&1", timeout=30)
    print(f"  SCP: {out.strip() or err.strip()}")
    
    # Wait
    time.sleep(5)

mac_client.close()

# Now extract on Windows
for i, filepath in enumerate(files):
    filename = filepath.split('/')[-1]
    print(f"\n[{i+1}/{len(files)}] Extract {filename}")
    
    # Upload via multipart
    with open(f"C:\\Users\\crazydb911\\{filename}", 'rb') as f:
        r = requests.post(
            f"http://{WIN_HOST}:8766/api/extract",
            files={"file": (filename, f)},
            data={"ssid": "BruceWen-5G"},
            timeout=30
        )
    print(f"  Upload: {r.json()}")
    
    # Wait for extraction
    time.sleep(10)
    
    # Check state
    r = requests.get(f"http://{WIN_HOST}:8766/api/state", timeout=10)
    d = r.json()
    print(f"  Status: {d['status']} - {d['message']}")
