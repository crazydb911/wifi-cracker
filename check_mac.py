import requests
try:
    r = requests.get('http://192.168.1.102:8765/api/state', timeout=5)
    d = r.json()
    print('Mac app: OK')
    print(f'Status: {d["status"]}')
    print(f'Message: {d["message"]}')
    print(f'APs: {len(d.get("ap_list", []))}')
except Exception as e:
    print(f'Mac app: FAILED ({e})')
