import requests, time

base = 'http://127.0.0.1:8766'
print('=== Windows App Verification ===')

# 1. Root page
r = requests.get(f'{base}/')
print(f'GET /           : {r.status_code} ({len(r.content)} bytes)')
assert r.status_code == 200 and 'WiFi Cracker' in r.text, "Root page failed"

# 2. State
d = requests.get(f'{base}/api/state').json()
print(f'GET /api/state  : OK (status={d["status"]}, gpu={d.get("gpu_temp")}C)')
assert 'status' in d and 'gpu_temp' in d, "State fields missing"

# 3. Extract
r = requests.post(f'{base}/api/extract',
    files={'file': ('t.pcapng', open(r'C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng','rb'))},
    data={'ssid': '32H9F_5G'})
print(f'POST /api/extract: {r.status_code} {r.json()}')
assert r.status_code == 200, "Extract failed"

time.sleep(8)
d = requests.get(f'{base}/api/state').json()
print(f'Extract result  : {d["message"]} (hashes={d["hash_count"]})')
assert d['hash_count'] == 6, f"Expected 6 hashes, got {d['hash_count']}"

# 4. Crack (short - rockonly)
r = requests.post(f'{base}/api/crack?wordlist=rockyou&rules=&mode=0&temp_limit=90')
print(f'POST /api/crack : {r.status_code} {r.json()}')
assert r.status_code == 200, "Crack start failed"

time.sleep(10)
d = requests.get(f'{base}/api/state').json()
print(f'Crack result    : {d["message"]}')
print(f'Results         : {d["results"]}')
print(f'GPU             : {d.get("gpu_temp")}C')

# 5. Stop
r = requests.post(f'{base}/api/stop')
print(f'POST /api/stop  : {r.status_code} {r.json()}')

print()
print('=== ALL WINDOWS APP TESTS PASSED ===')
