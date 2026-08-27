import requests
r = requests.get('http://127.0.0.1:8766/api/state', timeout=5)
d = r.json()
print(f'Status: {d["status"]}')
r = requests.get('http://127.0.0.1:8766/api/log', timeout=5)
log = r.json()
print(f'Log lines: {len(log["lines"])}')
print(f'Last log: {log["lines"][-1] if log["lines"] else "empty"}')
r = requests.get('http://127.0.0.1:8766/api/pcaps', timeout=5)
pcaps = r.json()
print(f'PCAPs: {len(pcaps["files"])}')
for f in pcaps["files"][:3]:
    print(f'  {f["name"]} ({f["size"]//1024}KB)')
print('ALL OK')
