"""Upload capture files to Windows and extract EAPOL."""
import requests, time

HOST = "192.168.1.102"
WIN_HOST = "192.168.1.107"

# Capture files to upload
files = [
    "/Users/crazydb911/cap_f8345a8c1f9f_1787845952.pcap",  # BruceWen-5G
    "/Users/crazydb911/cap_003192338022_1787845902.pcap",  # Han_5G
    "/Users/crazydb911/cap_3c7c3ff6e58c_1787845852.pcap",  # TP-LINK_lucien_5G
    "/Users/crazydb911/cap_a2ad9ff33820_1787845801.pcap",  # Kurt Home
]

# Upload each file to Windows
for i, filepath in enumerate(files):
    filename = filepath.split('/')[-1]
    print(f"\n[{i+1}/{len(files)}] {filename}")
    
    # Upload via Mac app (copy to Windows via SCP)
    r = requests.post(
        f"http://{HOST}:8765/api/control/run",
        params={"cmd": f"scp {filepath} crazydb911@{WIN_HOST}:/Users/crazydb911/ 2>&1", "sudo": False, "timeout": 30},
        timeout=40
    )
    result = r.json()
    print(f"  SCP: {result.get('ok')}")
    
    # Wait for SCP
    time.sleep(5)
    
    # Extract on Windows
    r = requests.post(
        f"http://{WIN_HOST}:8766/api/extract",
        params={"file": filename},
        timeout=30
    )
    print(f"  Extract: {r.json()}")
    
    # Wait for extraction
    time.sleep(10)
    
    # Check state
    r = requests.get(f"http://{WIN_HOST}:8766/api/state", timeout=10)
    d = r.json()
    print(f"  Status: {d['status']} - {d['message']}")
