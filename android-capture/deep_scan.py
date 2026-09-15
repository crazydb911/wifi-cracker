import sys
from collections import Counter
from scapy.all import rdpcap, Dot11
try:
    from scapy.layers.eap import EAPOL
    HAVE_EAPOL = True
except Exception:
    HAVE_EAPOL = False

path = sys.argv[1]
CLIENT = 'bc:61:93:23:bc:3f'   # sticky client
TARGET = 'bc:3e:07:01:dc:98'   # 32H10F 2.4G

SUB = {0:'auth',1:'assoc_req',2:'assoc_resp',3:'reauth',4:'reassoc_req',
       5:'reassoc_resp',7:'probe_req',8:'probe_resp',11:'deauth',12:'action'}

pk = rdpcap(path)
print('file:', path)
print('total:', len(pk))

eapol, assoc, clientf, target_assoc = [], [], [], []
bssid_count = Counter()
for p in pk:
    d = p.getlayer(Dot11)
    if d is None:
        continue
    da, sa, bssid = d.addr1, d.addr2, d.addr3
    if bssid:
        bssid_count[bssid] += 1
    if HAVE_EAPOL and p.haslayer(EAPOL):
        eapol.append('type=%d sub=%d da=%s sa=%s bssid=%s' % (d.type, d.subtype, da, sa, bssid))
    if d.type == 0:  # management
        nm = SUB.get(d.subtype, 'sub%d' % d.subtype)
        if d.subtype in (1, 2, 4, 5, 11, 0):
            assoc.append((nm, 'da=%s sa=%s bssid=%s' % (da, sa, bssid)))
        if bssid == TARGET and d.subtype in (2, 5):
            target_assoc.append('sub=%d(%s) da=%s sa=%s' % (d.subtype, nm, da, sa))
    if da == CLIENT or sa == CLIENT or bssid == CLIENT:
        clientf.append((d.type, d.subtype, 'da=%s sa=%s bssid=%s' % (da, sa, bssid)))

print('\nEAPOL frames:', len(eapol))
for e in eapol[:15]:
    print('   ', e)

print('\nmgmt subtype counts:')
subc = Counter()
for p in pk:
    d = p.getlayer(Dot11)
    if d and d.type == 0:
        subc[SUB.get(d.subtype, 'sub%d' % d.subtype)] += 1
for k, v in subc.most_common():
    print('   %-12s %d' % (k, v))

print('\nassoc/auth/deauth detail:')
shown = 0
for nm, s in assoc:
    if nm in ('assoc_req', 'assoc_resp', 'reassoc_req', 'reassoc_resp', 'deauth'):
        print('   %-12s %s' % (nm, s))
        shown += 1
        if shown >= 40:
            break

print('\nTARGET 32H10F (re)assoc responses:', len(target_assoc))
for t in target_assoc[:20]:
    print('   ', t)

print('\nframes involving client', CLIENT, ':', len(clientf))
seen = set()
for ct, cs, s in clientf:
    key = (ct, cs)
    if key not in seen:
        print('   t=%d sub=%d(%s) %s' % (ct, cs, SUB.get(cs, '?'), s))
        seen.add(key)
    if len(seen) >= 25:
        break

print('\nTop BSSIDs:')
for b, c in bssid_count.most_common(15):
    print('   %s: %d' % (b, c))