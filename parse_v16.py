#!/usr/bin/env python3
"""V16: check what msg=0 and msg=19 packets are."""
import struct

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"
TARGET_BSSID = b"\x6c\x4f\x89\x4c\xa0\xe4"

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

# Show first few msg=0 and msg=19 packets
count0 = count19 = 0
for i, pkt in enumerate(pkts):
    idx = pkt.find(b"\x88\x8e")
    if idx == -1: continue
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    msg = eapol[5]
    a1 = pkt[4:10]
    a3 = pkt[16:22]
    
    if msg == 0 and count0 < 3:
        count0 += 1
        a2 = pkt[10:16]
        print("pkt%03d msg=0 a1=%s a2=%s a3=%s eapol_len=%d" % (i, mac(a1), mac(a2), mac(a3), len(eapol)))
        print("  eapol[0:20]=%s" % eapol[:20].hex())
        print()
    
    elif msg == 19 and count19 < 3:
        count19 += 1
        a2 = pkt[10:16]
        print("pkt%03d msg=19 a1=%s a2=%s a3=%s eapol_len=%d" % (i, mac(a1), mac(a2), mac(a3), len(eapol)))
        print("  eapol[0:20]=%s" % eapol[:20].hex())
        print()
