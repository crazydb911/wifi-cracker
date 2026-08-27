"""Upload capture files to Windows (multipart) and extract EAPOL."""
import requests, time

WIN_HOST = "192.168.1.107"

# Capture files on Windows (already SCP'd)
files = [
    "cap_f8345a8c1f9f_1787845952.pcap",  # BruceWen-5G
    "cap_003192338022_1787845902.pcap",  # Han_5G
    "cap_3c7c3ff6e58c_1787845852.pcap",  # TP-LINK_lucien_5G
    "cap_a2ad9ff33820_1787845801.pcap",  # Kurt Home
]

# Upload each file to Windows (multipart)
for i, filename in enumerate(files):
    filepath = f"C:\\Users\\crazydb911\\{filename}"
    print(f"\n[{i+1}/{len(files)}] {filename}")
    
    # Upload via multipart
    with open(filepath, 'rb') as f:
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
