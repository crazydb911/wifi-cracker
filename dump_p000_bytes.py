#!/usr/bin/env python3
"""Dump exact byte positions of pkt000 to find where 888e is."""
import struct

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"

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
pkt = pkts[0]
print("pkt000 (%d bytes):" % len(pkt))
for i in range(0, len(pkt), 16):
    row = pkt[i:i+16]
    print("  %3d: %s" % (i, " ".join("%02x" % b for b in row)))

# Find 888e
idx = pkt.find(b"\x88\x8e")
print()
print("888e found at offset %d" % idx)
print("pkt[26:30]=%s" % pkt[26:30].hex())
print("pkt[28:32]=%s" % pkt[28:32].hex())
