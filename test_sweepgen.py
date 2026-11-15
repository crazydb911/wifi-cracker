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
# Preheat is now fully passive by design: every hcxdumptool start does its own
# interface mode init, and 7 of those inside the first 45s is the leading
# suspect for card life falling from seven minutes to 45 seconds.
chk('preheat issues ZERO hcxdumptool starts (mode-free)', s1.count('hcxdumptool') == 0,
    '(got %d)' % s1.count('hcxdumptool'))
chk('preheat captures passively on all 7 channels', s1.count('tcpdump -i wlan0') == 7,
    '(got %d)' % s1.count('tcpdump -i wlan0'))
chk('preheat still tunes each channel explicitly', s1.count('iw dev wlan0 set channel') >= 7,
    '(got %d)' % s1.count('iw dev wlan0 set channel'))
chk('preheat tunes the universal 2.4G set 1/6/11',
    all(('iw dev wlan0 set channel %d' % c) in s1 for c in (1, 6, 11)))
chk('stale 149/153 suppressed', '149b' not in s1 and '153b' not in s1)
chk('preheat budget under 60s', t1 < 60, '(got %ds)' % t1)
chk('txpower written at most once per session (ping-pong off)', s1.count('set txpower') <= 1,
    '(got %d)' % s1.count('set txpower'))
chk('rejected 5G back-off write removed', 'set txpower fixed 1000' not in s1)
chk('converters wrapped in timeout so a hang cannot eat the ssh budget',
    s1.count('timeout 20 hcxpcapngtool') >= 5, '(got %d)' % s1.count('timeout 20 hcxpcapngtool'))

print('=== steady round (map-driven) ===')
s2, t2 = ns['gen'](T(dict(oldmap), True))
print('  budget total=%ds  txpower writes=%d' % (t2, s2.count('set txpower')))
chk('no ifconfig down/up in generated script', 'ifconfig' not in s2)
chk('txpower written at most twice per round', s2.count('set txpower') <= 2)
chk('map channels restored (149 passive tcpdump)',
      'tcpdump -i wlan0' in s2 and 'set channel 149' in s2)
chk('steady round longer than preheat round', t2 > t1, '(%ds vs %ds)' % (t2, t1))
chk('steady round attacks actively on 2.4G (active suffix a)',
    'hcxdumptool -i wlan0 -c 1a' in s2 or 'hcxdumptool -i wlan0 -c 6a' in s2)
# The steady fixture map only carries 149/153, which are passive by design, so
# the active 5G branch needs its own AP on channel 36 to be exercised at all.
s3, t3 = ns['gen'](T(dict({
    'aa:bb:cc:00:00:05': ['HT40', 36, -48, now - 600],
    'aa:bb:cc:00:00:06': ['HT80', 44, -52, now - 600],
}), True))
chk('steady round attacks actively on 5G (active suffix b)',
    '-c 36b' in s3 and '-c 44b' in s3,
    '(36b=%s 44b=%s)' % ('-c 36b' in s3, '-c 44b' in s3))
chk('a 5G-bearing steady round still flushes per channel',
    s3.count('SWEEPCH') == s3.count('hcxpcapngtool'),
    '(markers=%d conv=%d)' % (s3.count('SWEEPCH'), s3.count('hcxpcapngtool')))
chk('no steady round re-writes txpower more than once',
    s3.count('set txpower') <= 1, '(got %d)' % s3.count('set txpower'))
chk('txpower re-armed for a fresh session then not repeated',
    s2.count('set txpower') <= 1, '(got %d)' % s2.count('set txpower'))

print('=== per-channel flush (card dies ~40s after enumeration) ===')
CAP = ('hcxdumptool -i wlan0', 'tcpdump -i wlan0')
pos = sorted([s1.find(k) for k in CAP for _ in [0]
              if s1.find(k) >= 0] +
             [i for i in range(len(s1))
              if s1.startswith(CAP, i)])
pos = sorted(set(pos))
chk('preheat round issues %d captures' % len(pos), len(pos) == 7, '(got %d)' % len(pos))
gaps = []
for a, b in zip(pos, pos[1:] + [len(s1)]):
    seg = s1[a:b]
    if 'hcxpcapngtool' not in seg or 'cat /tmp/sw' not in seg:
        gaps.append(a)
chk('every capture is followed by its own convert+cat', not gaps, str(gaps))
chk('per-channel marker emitted once per capture',
      s1.count('echo SWEEPCH') == len(pos),
      '(%d vs %d)' % (s1.count('echo SWEEPCH'), len(pos)))
first_flush = s1.find('hcxpcapngtool')
chk('first flush happens early in the script',
      first_flush > 0 and first_flush < len(s1) // 3,
      '(offset %d of %d)' % (first_flush, len(s1)))
chk('end-only bulk convert is gone',
      '/tmp/sw.22000' not in s1 and '/tmp/sw_*.pcapng*' not in s1)
chk('preheat budget fits inside measured 40s card life',
      t1 <= 40, '(got %ds)' % t1)
chk('steady round also flushes per channel',
      s2.count('echo SWEEPCH') == len([i for i in range(len(s2))
                                       if s2.startswith(CAP, i)]))

print('=== static: interface reset is opt-in only ===')
chk('IF_RESET default is opt-in file', "IF_RESET = os.path.exists" in src)
chk('ifreset.on gate present', 'ifreset.on' in src)
chk('no bare ifconfig outside IFR definition',
      src.count('ifconfig wlan0') == 2)

print()
print('RESULT: %s' % ('ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)))
