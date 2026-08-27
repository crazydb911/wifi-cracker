import requests, time

# Extract
r = requests.post('http://127.0.0.1:8766/api/extract',
    files={'file': ('x.pcapng', open(r'C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng','rb'))},
    data={'ssid': '32H9F_5G'})
print('Extract:', r.json())
time.sleep(8)

# Crack with temp limit 80 (to trigger throttle)
r = requests.post('http://127.0.0.1:8766/api/crack?wordlist=wifi_wordlist&rules=best66&mode=0&temp_limit=80')
print('Crack started:', r.json())

# Monitor thermal
for i in range(20):
    time.sleep(3)
    d = requests.get('http://127.0.0.1:8766/api/state').json()
    gpu = d.get('gpu_temp')
    status = d['status']
    msg = d['message'][:60]
    print(f'[{i*3:3d}s] GPU:{gpu}°C | {status} | {msg}')
    if status == 'idle' and i > 2:
        break
