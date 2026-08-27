"""Crack the new hash with wifi_wordlist + best66."""
import requests, time

# Check state
r = requests.get('http://127.0.0.1:8766/api/state', timeout=5)
d = r.json()
print(f"Hash file: {d['hash_file']}")
print(f"Hash count: {d['hash_count']}")

# Read hash
with open(d['hash_file']) as f:
    for line in f:
        print(f"Hash: {line.strip()[:120]}...")

# Start cracking with wifi_wordlist + best66
print("\nStarting crack (wifi_wordlist + best66)...")
r = requests.post(
    'http://127.0.0.1:8766/api/crack',
    params={'wordlist': 'wifi_wordlist', 'rules': 'best66', 'mode': '0', 'temp_limit': 85}
)
print(f"Crack: {r.json()}")

# Poll for results
for i in range(60):
    time.sleep(5)
    r = requests.get('http://127.0.0.1:8766/api/state', timeout=5)
    d = r.json()
    status = d['status']
    msg = d['message']
    results = d.get('results', [])
    gpu_temp = d.get('gpu_temp', '?')
    speed = d.get('speed', '')
    print(f"[{(i+1)*5}s] {status} | {msg[:60]} | GPU:{gpu_temp}°C | {speed[:40] if speed else ''}")
    if results and 'No match' not in results[0]:
        print(f"\n*** CRACKED: {results[0]} ***")
        break
    if status == 'idle' and i > 2:
        print(f"\nDone: {results}")
        break
