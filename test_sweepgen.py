import time

SRC = '/Users/tongbao/wifi_cracker/mac_wifi_app_v2.py'
src = open(SRC, encoding='utf-8').read()

sr = src.index('    def _sweep_round(self):')
nxt = src.index('    def ', sr + 10)
body = src[sr:nxt].replace('    def _sweep_round(self):', 'def gen(self):', 1)
cut = body.index('        try:\n            with self._cap_lock:')
body = body[:cut] + '        return script, total\n'

ns = {'BIND': '', 'CH': '', 'IFR': ''}
exec('import time\n' + body, ns)


class T:
    def __init__(self, aps, preheat):
        self.aps_seen = aps
        self.traffic = set()
        self._preheat = preheat
        self.target = None
        self.events = []

    def is_set(self):
        return False

    def _ev(self, tag, msg):
        self.events.append(tag)

    def _traffic_bssids(self):
        return set()

    @property
    def _running(self):
        return self

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
        raise AttributeError(k)


now = time.time()
oldmap = {
    'aa:bb:cc:00:00:01': ['OLD1', 149, -50, now - 3 * 86400],
    'aa:bb:cc:00:00:02': ['OLD2', 153, -55, now - 3 * 86400],
    'aa:bb:cc:00:00:03': ['OLD3', 4, -60, now - 3 * 86400],
    'aa:bb:cc:00:00:04': ['OLD4', 6, -45, now - 3600],
}

fails = []


def chk(name, cond, detail=''):
    print('  %-46s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
    if not cond:
        fails.append(name)


print('=== preheat round (phy just woke) ===')
s1, t1 = ns['gen'](T(dict(oldmap), False))
print('  budget total=%ds  txpower writes=%d  ifconfig=%d'
      % (t1, s1.count('set txpower'), s1.count('ifconfig')))
chk('no ifconfig down/up in generated script', 'ifconfig' not in s1)
chk('txpower written at most twice per round', s1.count('set txpower') <= 2)
chk('5G uses active hcxdumptool (36b/40b/44b/48b)',
      all(('-c %db ' % c) in s1 for c in (36, 40, 44, 48)))
chk('2.4G covers universal 1/6/11',
      all(('-c %da ' % c) in s1 for c in (1, 6, 11)))
chk('stale 149/153 suppressed', '149b' not in s1 and '153b' not in s1)
chk('preheat budget under 60s', t1 < 60, '(got %ds)' % t1)

print('=== steady round (map-driven) ===')
s2, t2 = ns['gen'](T(dict(oldmap), True))
print('  budget total=%ds  txpower writes=%d' % (t2, s2.count('set txpower')))
chk('no ifconfig down/up in generated script', 'ifconfig' not in s2)
chk('txpower written at most twice per round', s2.count('set txpower') <= 2)
chk('map channels restored (149 passive tcpdump)',
      'tcpdump -i wlan0' in s2 and 'set channel 149' in s2)
chk('steady round longer than preheat round', t2 > t1, '(%ds vs %ds)' % (t2, t1))

print('=== static: interface reset is opt-in only ===')
chk('IF_RESET default is opt-in file', "IF_RESET = os.path.exists" in src)
chk('ifreset.on gate present', 'ifreset.on' in src)
chk('no bare ifconfig outside IFR definition',
      src.count('ifconfig wlan0') == 2)

print()
print('RESULT: %s' % ('ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)))
