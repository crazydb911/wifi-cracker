"""Wait for Mac to reconnect, then check capture result."""
import requests, time

HOST = "192.168.1.102"

# Wait for Mac to reconnect
print("Waiting for Mac to reconnect...")
for i in range(60):  # 5 min max
    time.sleep(5)
    try:
        r = requests.get(f"http://{HOST}:8765/api/state", timeout=5)
        d = r.json()
        print(f"  [{(i+1)*5}s] {d['status']} - {d['message']}")
        
        if d['status'] == 'idle' and d.get('capture_file'):
            print(f"\nCapture file: {d['capture_file']}")
            print(f"EAPOL count: {d.get('capture_eapol_count', 0)}")
            print(f"EAPOL target: {d.get('capture_eapol_target', 0)}")
            
            # Upload
            if d.get('capture_eapol_target', 0) > 0:
                print("\nUploading to Windows...")
                r = requests.post(f"http://{HOST}:8765/api/upload", timeout=10)
                print(f"Response: {r.json()}")
            break
    except Exception as e:
        print(f"  [{(i+1)*5}s] {str(e)[:50]}")
