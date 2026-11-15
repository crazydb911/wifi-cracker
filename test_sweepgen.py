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
# Cold round is active-first by design. The guest log shows transmit dying
# (TX status FIFO -EPROTO, every 5.0s retry failing) while reception keeps
# working, so a passive preheat spends the only healthy window proving
# nothing about the one thing that is broken. hcxdumptool takes a channel
# list natively -- its help reads "-c <digit> : set channel (1a,2a,36b,...)
# default: 1a,6a,11a" -- so one process hops internally and pays the
# interface mode init once per band instead of once per channel.
chk('cold round goes active on both bands', s1.count('hcxdumptool -i wlan0') == 3,
    '(got %d)' % s1.count('hcxdumptool -i wlan0'))
chk('cold round issues no tcpdump', 'tcpdump -i wlan0' not in s1)
chk('cold round hops with channel lists',
    '-c 1a,6a,11a' in s1 and '-c 36b,40b,44b,48b' in s1)
chk('cold round puts the injection question to the tool itself',
    s1.count('--rcascan=active') == 2, '(got %d)' % s1.count('--rcascan=active'))
chk('harvest stops on the first PMKID', s1.count('--exitoneapol=1') == 1)
chk('errormax raised off the default 100', s1.count('--errormax=100000') == 3,
    '(got %d)' % s1.count('--errormax=100000'))
chk('cold round does not re-tune per channel', 'iw dev wlan0 set channel' not in s1)
chk('tx/rx counters bracket the captures',
    s1.find('TXRX0 ') >= 0 and s1.find('TXRX1 ') > max(
        i for i in range(len(s1)) if s1.startswith('hcxdumptool', i)))
chk('stale 149/153 suppressed', '149b' not in s1 and '153b' not in s1)
chk('txpower written at most once per session (ping-pong off)', s1.count('set txpower') <= 1,
    '(got %d)' % s1.count('set txpower'))
chk('rejected 5G back-off write removed', 'set txpower fixed 1000' not in s1)
chk('converters wrapped in timeout so a hang cannot eat the ssh budget',
    s1.count('timeout 20 hcxpcapngtool') == 3, '(got %d)' % s1.count('timeout 20 hcxpcapngtool'))

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

print('=== per-phase flush (card dies ~45s after enumeration) ===')
pos = sorted(set(i for i in range(len(s1)) if s1.startswith('hcxdumptool', i)))
chk('cold round issues %d captures' % len(pos), len(pos) == 3, '(got %d)' % len(pos))
gaps = []
for a, b in zip(pos, pos[1:] + [len(s1)]):
    if 'hcxpcapngtool' not in s1[a:b]:
        gaps.append(a)
chk('every capture is followed by its own convert', not gaps, str(gaps))
chk('each phase writes a distinct pcapng',
      all(('-w /tmp/cold%d.pcapng ' % k) in s1 for k in (1, 2, 3)))
chk('each convert cats its hashes back through ssh',
      s1.count('cat /tmp/cold') == 3, '(got %d)' % s1.count('cat /tmp/cold'))
first_flush = s1.find('hcxpcapngtool')
chk('first flush lands before the 5G phase',
      0 < first_flush < s1.find('-c 36b,40b,44b,48b'),
      '(offset %d)' % first_flush)
# The cold round is deliberately longer than the measured 45s card life.
# Each phase converts and cats on its own, so a card that dies during the
# 5G phase still delivers the 2.4G hashes over ssh. What must never come
# back is an end-only bulk convert, which is how a whole round was lost.
chk('no end-only bulk convert',
      '/tmp/sw.22000' not in s1 and 'cat /tmp/sw' not in s1)
chk('cold budget stays inside the ssh timeout', t1 <= 145, '(got %ds)' % t1)
CAP2 = ('hcxdumptool -i wlan0', 'tcpdump -i wlan0')
chk('steady round also flushes per channel',
      s2.count('echo SWEEPCH') == len([i for i in range(len(s2))
                                       if s2.startswith(CAP2, i)]))

print('=== static: interface reset is opt-in only ===')
chk('IF_RESET default is opt-in file', "IF_RESET = os.path.exists" in src)
chk('ifreset.on gate present', 'ifreset.on' in src)
chk('no bare ifconfig outside IFR definition',
      src.count('ifconfig wlan0') == 2)

print()
print('RESULT: %s' % ('ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)))
