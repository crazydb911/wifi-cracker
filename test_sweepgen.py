import re
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
chk('cold round goes active on both bands', s1.count('hcxdumptool -i wlan0') == 4,
    '(got %d)' % s1.count('hcxdumptool -i wlan0'))
chk('cold round issues no tcpdump', 'tcpdump -i wlan0' not in s1)
chk('cold round hops with channel lists',
    '-c 1a,6a,11a' in s1 and '-c 36b,40b,44b,48b' in s1)
chk('cold round puts the injection question to the tool itself',
    s1.count('--rcascan=active') == 2, '(got %d)' % s1.count('--rcascan=active'))
chk('harvest stops on the first PMKID', s1.count('--exitoneapol=1') == 2,
    '(got %d)' % s1.count('--exitoneapol=1'))
chk('errormax raised off the default 100', s1.count('--errormax=100000') == 4,
    '(got %d)' % s1.count('--errormax=100000'))
chk('cold round does not re-tune per channel', 'iw dev wlan0 set channel' not in s1)
# TXRX1 sits after the two harvests, not after the rcascan verdicts: the
# counters measure what the captures saw, and a verdict run adds no packets
# to the asset.
chk('tx/rx counters bracket the captures',
    s1.find('TXRX0 ') >= 0 and s1.find('TXRX1 ') > max(
        s1.index('-w /tmp/cold1.pcapng'), s1.index('-w /tmp/cold2.pcapng')))
chk('both harvests land before either verdict',
    max(s1.index('-w /tmp/cold1.pcapng'), s1.index('-w /tmp/cold2.pcapng'))
    < s1.index('echo RCASCAN24_START'))
chk('stale 149/153 suppressed', '149b' not in s1 and '153b' not in s1)
chk('txpower written at most once per session (ping-pong off)', s1.count('set txpower') <= 1,
    '(got %d)' % s1.count('set txpower'))
chk('rejected 5G back-off write removed', 'set txpower fixed 1000' not in s1)
chk('converters wrapped in timeout so a hang cannot eat the ssh budget',
    s1.count('timeout 15 hcxpcapngtool') == 2, '(got %d)' % s1.count('timeout 20 hcxpcapngtool'))

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
inv = []
for i in range(len(s1)):
    if s1.startswith('hcxdumptool', i):
        j = s1.find('\n', i)
        inv.append(s1[i:j if j > 0 else len(s1)])
# hcxdumptool.c calls exit(EXIT_FAILURE) when --rcascan and -w appear
# together, in either order (proven against the installed binary). A phase
# that paired them captured nothing, and the round would have reported a
# dead radio when the real cause was the tool's own argument check.
chk('no invocation pairs --rcascan with -w',
    not any('--rcascan' in x and ' -w ' in x for x in inv),
    str([x[:60] for x in inv if '--rcascan' in x and ' -w ' in x]))
chk('verdict runs carry --rds=5, harvest runs --rds=4',
    all('--rds=5' in x for x in inv if '--rcascan' in x)
    and all('--rds=4' in x for x in inv if ' -w ' in x))
pos = sorted(set(i for i in range(len(s1)) if s1.startswith('hcxdumptool', i)
                 and ' -w ' in (lambda j: s1[i:j if j > 0 else len(s1)])(s1.find('\n', i))))
chk('cold round issues %d captures' % len(pos), len(pos) == 2, '(got %d)' % len(pos))
gaps = []
for a, b in zip(pos, pos[1:] + [len(s1)]):
    if 'hcxpcapngtool' not in s1[a:b]:
        gaps.append(a)
chk('every capture is converted in the same round',
    all('hcxpcapngtool' in s1[a:] for a in pos), str(pos))
chk('each phase writes a distinct pcapng',
      all(('-w /tmp/cold%d.pcapng ' % k) in s1 for k in (1, 2)))
chk('each convert cats its hashes back through ssh',
      s1.count('cat /tmp/cold') == 2, '(got %d)' % s1.count('cat /tmp/cold'))
first_flush = s1.find('hcxpcapngtool')
# The invariant moved. Conversion no longer trails each capture; it trails
# every operation that needs a living radio. A conversion costs the card
# nothing, so spending the harvest window on one was spending the only
# scarce resource on work that could wait. It could not wait when the hash
# was the only thing that ever left the guest -- the capture pull below is
# what makes waiting safe, so both are asserted together.
radio_end = max(s1.index('echo RCASCAN5G_DONE'), s1.index('-w /tmp/cold2.pcapng'))
conv_start = min(s1.index('hcxpcapngtool --all -o /tmp/cold1'),
                 s1.index('hcxpcapngtool --all -o /tmp/cold2'))
chk('all radio work precedes all conversion', radio_end < conv_start,
    'radio_end=%d conv_start=%d' % (radio_end, conv_start))
chk('the raw capture is pulled out of the guest',
    "_pull_guest_caps('/newroot/tmp/cold*.pcapng*', 'cold')" in src)
chk('pulled captures are removed from the guest so the disk cannot fill',
    "rm', '-f', p" in src)
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

print('=== converter write path == read-back path (the /g/tmp defect) ===')
# hcxpcapngtool wrote /g/tmp/X.22000 while the app cat-ed /tmp/X.22000, and
# nothing in the tree ever created /g. Proven in the guest: "ls: /g: No such
# file or directory". The failure went to a swallowed stderr, so every path
# silently harvested zero hashes. Pairing is checked, not assumed.
bad = []
for m in re.finditer(r'-o (\S+?\.22000)', s1):
    w = m.group(1)
    if not s1.count('cat ' + w):
        bad.append(('no_cat', w))
    if '/g/' in w:
        bad.append(('g_dir', w))
chk('every converter output is read back from the same path', not bad, str(bad))
chk('no path depends on a directory nothing creates', '/g/tmp' not in s1)


# ssh joins argv with spaces and hands the result to one remote shell, so any
# quoting in an argument is destroyed in transit. 'sh -c "ls /a/*.pcap"'
# arrives as sh -c with a bare ls and the glob as an unread positional: the
# listing comes back empty and the caller reads that as 'no files'. Every
# guest call here must carry its script on stdin instead.
def _ssh_sh_c(s):
    # Only the ssh path loses quoting: ssh joins argv with spaces and hands
    # one string to the remote shell. A local sh -c is fine and there are
    # six of those for ioreg and the monitor, so the guard has to be
    # scoped to the calls that actually cross the wire.
    bad = []
    L = s.split(chr(10))
    needle = "['sh', '-c']"
    for n, t in enumerate(L):
            if needle in chr(10).join(L[n:n + 3]):
                bad.append(n + 1)
    return bad

chk('no guest call uses sh -c', not _ssh_sh_c(src),
    'lines ' + str(_ssh_sh_c(src)))

# The capture pull is the only reason conversion can be deferred out of the
# harvest window, so it has to be asserted to exist for both capture paths,
# not just the one that was tested when it was written.
chk('both the cold path and a catch-all rescue pull from the guest',
    "'cold')" in src and "'rescue')" in src
    and src.count('_pull_guest_caps(') >= 3,
    'pulls=%d' % src.count('_pull_guest_caps('))
print('=== static: interface reset is opt-in only ===')
chk('IF_RESET default is opt-in file', "IF_RESET = os.path.exists" in src)
chk('ifreset.on gate present', 'ifreset.on' in src)
chk('no bare ifconfig outside IFR definition',
      src.count('ifconfig wlan0') == 2)

print()
print('RESULT: %s' % ('ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)))
