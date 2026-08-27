#!/usr/bin/env python3
"""V9: dump bytes around the MIC region in M1 and M3."""
import struct

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"
TARGET_BSSID = b"\x6c\x4f\x89\x4c\xa0\xe4"

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

m1_found = m3_found = False
for i, pkt in enumerate(pkts):
    idx = pkt.find(b"\x88\x8e")
    if idx == -1: continue
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    msg = eapol[5]
    a3 = pkt[16:22]
    if a3 != TARGET_BSSID: continue
    
    if msg == 1 and not m1_found:
        m1_found = True
        print("pkt%03d M1 (%d bytes EAPOL):" % (i, len(eapol)))
        for off in range(50, min(100, len(eapol)), 16):
            row = eapol[off:off+16]
            print("  %3d: %s" % (off, " ".join("%02x" % b for b in row)))
        print()
    
    elif msg == 3 and not m3_found:
        m3_found = True
        print("pkt%03d M3 (%d bytes EAPOL):" % (i, len(eapol)))
        for off in range(50, min(105, len(eapol)), 16):
            row = eapol[off:off+16]
            print("  %3d: %s" % (off, " ".join("%02x" % b for b in row)))
        print()
    
    if m1_found and m3_found:
        break
