"""Upload all capture files to Windows and extract EAPOL."""
import requests, time

HOST = "192.168.1.102"
WIN_HOST = "192.168.1.107"

# Get list of capture files
import paramiko

key = paramiko.Ed25519Key.from_private_key_file(r"C:\Users\crazydb911\.ssh\opremote_ed25519")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username="crazydb911", pkey=key, timeout=15)

def ssh(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# List all capture files
out, _ = ssh("ls -lt /Users/crazydb911/cap_*.pcap 2>/dev/null")
print("Capture files:")
files = []
for line in out.strip().split('\n'):
    if line.strip():
        parts = line.split()
        if len(parts) >= 9:
            filepath = parts[-1]
            files.append(filepath)
            print(f"  {filepath}")

client.close()

# Upload each file to Windows
print(f"\nUploading {len(files)} files to Windows...")
for i, filepath in enumerate(files):
    filename = filepath.split('/')[-1]
    print(f"\n[{i+1}/{len(files)}] {filename}")
    
    # Upload via Mac app
    r = requests.post(
        f"http://{HOST}:8765/api/control/run",
        params={"cmd": f"curl -s -X POST -F 'file=@{filepath}' http://{WIN_HOST}:8766/api/upload", "sudo": False, "timeout": 30},
        timeout=40
    )
    result = r.json()
    print(f"  Upload: {result.get('ok')}")
    if result.get('output'):
        print(f"  {result['output'].strip()}")
    
    # Wait for Windows to extract
    time.sleep(5)
