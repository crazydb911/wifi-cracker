#!/usr/bin/env python3
"""V18: final parser with correct a3 for M2.
   
   M1 (msg=1): AP->STA, a3=6c:4f:89:4c:a0:e4 (BSSID)
   M2 (msg=0): STA->AP, a3=60:f8:1d:ad:01:e4 (different MAC)
   M3 (msg=3): STA->AP, a3=6c:4f:89:4c:a0:e4 (BSSID)
"""
import struct, os

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"
AP_MAC_1 = b"\x6c\x4f\x89\x4c\xa0\xe4"  # a3 for M1/M3
AP_MAC_2 = b"\x60\xf8\x1d\xad\x01\xe4"  # a3 for M2
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
    
    if msg == 1 and a3 == AP_MAC_1:
        m1_count += 1
        o = 6
        anonce = eapol[o:o+32]; o += 32
        if anonce != b"\x00"*32:
            if best_m1 is None:
                best_m1 = (i, anonce, a1)
    
    elif msg == 0 and a3 == AP_MAC_2:
        m2_count += 1
        o = 6
        snonce = eapol[o:o+32]; o += 32
        if snonce != b"\x00"*32:
            if best_m2 is None:
                best_m2 = (i, snonce, a1)
    
    elif msg == 3 and a3 == AP_MAC_1:
        m3_count += 1
        o = 6
        anonce = eapol[o:o+32]; o += 32
        snonce = eapol[o:o+32]; o += 32
        if anonce != b"\x00"*32:
            if best_m3 is None:
                best_m3 = (i, anonce, snonce, a1)

print("M1=%d M2=%d M3=%d" % (m1_count, m2_count, m3_count))

if best_m1 and best_m3:
    idx1, anonce1, sta1 = best_m1
    idx3, anonce3, snonce3, sta3 = best_m3
    
    anonce = anonce3
    snonce = snonce3
    sta = sta1
    ap = AP_MAC_1
    
    print()
    print("=== Final hash data ===")
    print("ESSID: %s" % ESSID)
    print("AP MAC: %s" % mac(ap))
    print("STA MAC: %s" % mac(sta))
    print("ANonce: %s" % h(anonce))
    print("SNonce: %s" % h(snonce))
    print("KeyMic: (zeros - not present in frames)")
    
    hash_line = "%s:%s:%s:%s:%s:%s:%s:%s:%s" % (
        ESSID, mac(ap), mac(sta), h(anonce), h(snonce),
        "00000000000000000000000000000000",
        "00000000000000000000000000000000",
        "00000000000000000000000000000000",
        "00000000000000000000000000000000"
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
