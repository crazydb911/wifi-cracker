#!/usr/bin/env python3
"""Check all a3 values for M2 (msg=0) packets."""
import struct

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"

def mac(b): return ":".join("%02x" % x for x in b)

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

a3_counts = {}
for i, pkt in enumerate(pkts):
    idx = pkt.find(b"\x88\x8e")
    if idx == -1: continue
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    msg = eapol[5]
    a3 = pkt[16:22]
    
    if msg == 0:  # M2
        a3_counts[a3.hex()] = a3_counts.get(a3.hex(), 0) + 1

print("M2 (msg=0) a3 values:")
for k, v in sorted(a3_counts.items()):
    print("  %s: %d packets" % (":".join("%02x" % x for x in bytes.fromhex(k)), v))
