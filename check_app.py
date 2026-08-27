import requests, time

# Extract
r = requests.post('http://127.0.0.1:8766/api/extract',
    files={'file': ('x.pcapng', open(r'C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng','rb'))},
    data={'ssid': '32H9F_5G'})
print('Extract:', r.json())

time.sleep(8)
d = requests.get('http://127.0.0.1:8766/api/state').json()
print('Status:', d['status'], '| Hashes:', d['hash_count'])

# Start crack
r = requests.post('http://127.0.0.1:8766/api/crack?wordlist=wifi_wordlist&rules=best66&mode=0')
print('Crack started:', r.json())

# Monitor
for i in range(12):
    time.sleep(5)
    d = requests.get('http://127.0.0.1:8766/api/state').json()
    print(f'[{i*5}s] {d["status"]} | {d["message"][:80]} | GPU:{d.get("gpu_temp")}')
