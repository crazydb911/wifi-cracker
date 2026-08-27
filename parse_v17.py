#!/usr/bin/env python3
"""V17: final parser with all msgnum values.
   
   msg=1 (M1): AP->STA, body: anonce(32) apaddr(6) ssid(32) [mic(16) keydata(...)]
   msg=0 (M2): STA->AP, body: snonce(32) [keydata(...)]
   msg=3 (M3): STA->AP, body: anonce(32) snonce(32) [mic(16) keydata(...)]
   msg=19 (M4): AP->STA, body: [keydata(...)]
   
   For hashcat 22000, we need:
   - ANonce from M1
   - SNonce from M2 or M3
   - KeyMic from M3 (if present, else zeros)
"""
import struct, os

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"
TARGET_BSSID = b"\x6c\x4f\x89\x4c\xa0\xe4"
ESSID = "32H9F_5G"

def mac(b): return ":".join("%02x" % x for x in b)
def h(b): return b.hex()

def read_pkts(path):
    d = open(path, "rb").read()
    pkts = []
    off = 0
    n = len(d)
    while off + 8 <= n:
        blktype = struct.unpack("<I", d[off:off+4])[0]
        blklen = struct.unpack("<I", d[off+4:off+8])[0]
        if blklen < 12 or off + blklen > n: break
        if blktype == 0x00000006:
            body = d[off+8:off+blklen-4]
            pkts.append(body[4:])
        off += blklen
    return pkts

pkts = read_pkts(PATH)
print("packets:", len(pkts))

best_m1 = None
best_m2 = None
best_m3 = None
m1_count = m2_count = m3_count = 0

for i, pkt in enumerate(pkts):
    idx = pkt.find(b"\x88\x8e")
    if idx == -1: continue
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    msg = eapol[5]
    a1 = pkt[4:10]
    a3 = pkt[16:22]
    
    if msg == 1 and a3 == TARGET_BSSID:
        m1_count += 1
        o = 6
        anonce = eapol[o:o+32]; o += 32
        if anonce != b"\x00"*32:
            if best_m1 is None:
                best_m1 = (i, anonce, a1)
    
    elif msg == 0 and a3 == TARGET_BSSID:
        m2_count += 1
        o = 6
        snonce = eapol[o:o+32]; o += 32
        if snonce != b"\x00"*32:
            if best_m2 is None:
                best_m2 = (i, snonce, a1)
    
    elif msg == 3 and a3 == TARGET_BSSID:
        m3_count += 1
        o = 6
        anonce = eapol[o:o+32]; o += 32
        snonce = eapol[o:o+32]; o += 32
        if anonce != b"\x00"*32:
            if best_m3 is None:
                best_m3 = (i, anonce, snonce, a1)

print("M1(target)=%d M2(target)=%d M3(target)=%d" % (m1_count, m2_count, m3_count))

if best_m1 and best_m3:
    idx1, anonce1, sta1 = best_m1
    idx3, anonce3, snonce3, sta3 = best_m3
    
    # Use M3's anonce and snonce
    anonce = anonce3
    snonce = snonce3
    sta = sta1  # from M1 (dst = STA)
    ap = TARGET_BSSID
    
    print()
    print("=== Final hash data ===")
    print("ESSID: %s" % ESSID)
    print("AP MAC: %s" % mac(ap))
    print("STA MAC: %s" % mac(sta))
    print("ANonce: %s" % h(anonce))
    print("SNonce: %s" % h(snonce))
    print("KeyMic: (zeros - not present in frames)")
    
    # hashcat 22000: ESSID:AP:STA:ANonce:SNonce:KeyMicAP:KeyMicSTA:EKeyAP:EKeySTA
    hash_line = "%s:%s:%s:%s:%s:%s:%s:%s:%s" % (
        ESSID, mac(ap), mac(sta), h(anonce), h(snonce),
        "00000000000000000000000000000000",  # KeyMic AP
        "00000000000000000000000000000000",  # KeyMic STA
        "00000000000000000000000000000000",  # EKey AP
        "00000000000000000000000000000000"   # EKey STA
    )
    print()
    print("hashcat 22000 hash:")
    print(hash_line)
    
    hashdir = r"C:\Users\crazydb911\Documents\deepseek\hashes"
    if not os.path.exists(hashdir): os.makedirs(hashdir)
    hashfile = os.path.join(hashdir, "32h9f.22000")
    with open(hashfile, "w") as f:
        f.write(hash_line + "\n")
    print("Wrote %s" % hashfile)
