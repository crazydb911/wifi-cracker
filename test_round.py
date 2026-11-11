import ast

SRC = '/Users/tongbao/wifi_cracker/mac_wifi_app_v2.py'
src = open(SRC, encoding='utf-8').read()
fails = []


def chk(name, cond, detail=''):
    print('  %-48s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
    if not cond:
        fails.append(name)


print('=== A1: bssid -> tcpdump MAC formatting ===')
# the old expression, verbatim, with the local-`i` it depended on
old = "':'.join(bssid[i:i + 2]) if bssid else ''"
try:
    bssid = 'aabbccddeeff'
    i = None
    del i
    eval(old)
    chk('old expression raises', False, 'did not raise')
except UnboundLocalError as e:
    chk('old expression raised UnboundLocalError', True, '-> ' + str(e))
except NameError as e:
    chk('old expression raised NameError (same class of bug)', True, str(e))

new = ("bs = (bssid or '').replace(':', '').lower(); "
       "bssid_c = (':'.join(bs[j:j + 2] for j in range(0, len(bs) - 1, 2))"
       " if len(bs) >= 12 else '')")
for raw, want in [('aabbccddeeff', 'aa:bb:cc:dd:ee:ff'),
                  ('AA:BB:CC:DD:EE:FF', 'aa:bb:cc:dd:ee:ff'),
                  ('', ''), (None, ''), ('aabb', '')]:
    ns = {'bssid': raw}
    exec(new, ns)
    got = ns['bssid_c']
    chk('bssid %-18r -> %r' % (raw, want), got == want, 'got %r' % got)

print('=== A2: RCA txpower is band-gated, not per-channel ===')
t = ast.parse(src)
for n in ast.walk(t):
    if isinstance(n, ast.FunctionDef) and n.name == '_rca_round':
        seg = ast.get_source_segment(src, n)
        chk('txpower write guarded by last_pow',
            'if pow_ == last_pow' in seg)
        chk('last_pow initialised before the loop',
            seg.index('last_pow = None') < seg.index('for c in top:'))
        chk('no unconditional per-channel txpower write',
            "(CH + 'iw dev wlan0 set txpower fixed ' +\n"
            "                       ('1000' if c > 14 else '3000')"
            not in seg)

print('=== A3: scan script has balanced for/done ===')
for n in ast.walk(t):
    if isinstance(n, ast.FunctionDef) and n.name == '_scan_now':
        seg = ast.get_source_segment(src, n)
        chk('exactly one done terminator', seg.count("'done\\n')") == 1)
        chk('no stray double done', 'done\\ndone' not in seg)

print('=== C1: UI error log no longer uses an out-of-scope NL ===')
for n in ast.walk(t):
    if isinstance(n, ast.FunctionDef) and n.name == '_log':
        seg = ast.get_source_segment(src, n)
        if 'mac_wifi_ui_err' in seg:
            chk('uses chr(10) not bare NL', 'chr(10)' in seg and '+ NL)' not in seg)

print('=== C5: WPA*01 matched on MAC_AP (field 3) ===')
chk('no f[2] == b left', 'f[2] == b' not in src)
chk('f[3].lower() == b present', src.count('f[3].lower() == b') == 2)

print()
print('RESULT: %s' % ('ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)))
