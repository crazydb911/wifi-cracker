import re, json, time, os

SRC = '/Users/tongbao/wifi_cracker/mac_wifi_app_v2.py'
src = open(SRC, encoding='utf-8').read()
sr = src.index('    def _sweep_round(self):')
end = src.index('        script = (BIND +', sr)
body = src[sr:end]
body = body.replace('    def _sweep_round(self):', 'def pick(self):', 1)
body = body.replace('self._traffic_bssids()', 'self.traffic')
body = body.replace('self._ev(', 'self.ev(')

ns = {}
exec('import time\n' + body, ns)


class T:
    def __init__(self, aps, traffic, preheat):
        self.aps_seen = aps
        self.traffic = traffic
        self._preheat = preheat
        self.events = []

    def ev(self, tag, msg):
        self.events.append(tag + ' ' + msg)

    def _ch_w(self, n, g, ts):
        w = n + max(0, g + 90) // 2
        age = time.time() - (ts or 0)
        if age > 604800:
            w //= 4
        elif age > 86400:
            w //= 2
        elif age > 21600:
            w = (w * 3) // 4
        return max(1, w)

    def __getattr__(self, k):
        return []


now = time.time()
# an OLD town's map: nothing on ch1/6/11, 5G only on 149 (DFS, passive-only)
oldmap = {
    'aa:bb:cc:00:00:01': ['OLDTOWN', 149, -50, now - 3 * 86400],
    'aa:bb:cc:00:00:02': ['OLDTOWN2', 153, -55, now - 3 * 86400],
    'aa:bb:cc:00:00:03': ['OLDTOWN3', 4, -60, now - 3 * 86400],
}

print('=== OLD map, preheat OFF (first round after phy wake) ===')
t = T(dict(oldmap), set(), False)
r = ns['pick'](t)
print('  2.4G:', t.aps_seen and 'n/a', '| events:', t.events)

# re-run capturing the actual overridden dicts by re-exec with introspection
def run(preheat, aps):
    t = T(dict(aps), set(), preheat)
    ns['pick'](t)
    return t


t1 = run(False, oldmap)
print('  preheat event fired :', any('preheat' in e for e in t1.events))

t2 = run(True, oldmap)
print('  preheat event fired :', any('preheat' in e for e in t2.events), '(want False)')

# prove the emitted channel set by scraping the script build
def chans_of(preheat, aps):
    t = T(dict(aps), set(), preheat)
    g = {'time': time}
    b = body + chr(10) + "        return chans, ch5" + chr(10)
    ns2 = {}
    exec('import time\n' + b, ns2)
    return ns2['pick'](t)


print()
print('=== emitted channels, OLD map ===')
c24, c5 = chans_of(False, oldmap)
print('  preheat OFF -> 2.4G', sorted(c24), '5G', sorted(c5))
c24b, c5b = chans_of(True, oldmap)
print('  preheat ON  -> 2.4G', sorted(c24b), '5G', sorted(c5b))

ok = (sorted(c24) == [1, 6, 11] and sorted(c5) == [36, 40, 44, 48])
print()
print('  preheat forces universal set      :', 'PASS' if ok else 'FAIL')
print('  preheat suppresses stale 149/153   :', 'PASS' if not (set(c5) & {149, 153}) else 'FAIL')
print('  map still used once preheated     :', 'PASS' if sorted(c5b) == [149, 153] else 'FAIL')
