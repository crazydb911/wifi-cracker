import json, time, types

src = open('/Users/tongbao/wifi_cracker/mac_wifi_app_v2.py', encoding='utf-8').read()


def grab(start, end):
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


sr = src.index('    def _sweep_round(self):')
ch_w = grab('    def _ch_w(self, n, g, ts):', '    def _sweep_round(self):')
k = src.index('        traffic = self._traffic_bssids()', sr)
body = src[k:src.index('        script = (BIND +', k)]

ns = {'time': time, 'BIND': ''}
exec('class T:\n' + ch_w + '\n    def __getattr__(self, k):\n'
     '        return []\n'
     '\n    def round(self, aps_seen, traffic):\n'
     + '        self.aps_seen = aps_seen\n'
     + body.replace('self._traffic_bssids()', 'traffic')
     + '\n        return chans, ch5\n', ns)

d = json.load(open('/Users/tongbao/wifi_cracker/aps_seen.json'))
t = ns['T']()
chans, ch5 = t.round(d, set())
print('APS', len(d))
print('2.4G chans', dict(sorted(chans.items(), key=lambda kv: -kv[1])))
print('5G   chans', ch5)
assert chans, 'empty 2.4G channel plan'
assert all(isinstance(v, int) and v >= 1 for v in chans.values())
print('OK channel plan built from real 7-day map')
