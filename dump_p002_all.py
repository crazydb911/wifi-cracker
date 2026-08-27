#!/usr/bin/env python3
"""Dump pkt002 in full to understand the M3 structure."""
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
pkt = pkts[2]
print("pkt002 (%d bytes):" % len(pkt))
for i in range(0, len(pkt), 16):
    row = pkt[i:i+16]
    print("  %3d: %s" % (i, " ".join("%02x" % b for b in row)))

print()
# 802.11 header
fctl = struct.unpack("<H", pkt[0:2])[0]
dur = struct.unpack("<H", pkt[2:4])[0]
a1 = pkt[4:10]
a2 = pkt[10:16]
a3 = pkt[16:22]
a4 = pkt[22:28]
print("fctl=0x%04x dur=%d" % (fctl, dur))
print("a1=%s" % ":".join("%02x" % x for x in a1))
print("a2=%s" % ":".join("%02x" % x for x in a2))
print("a3=%s" % ":".join("%02x" % x for x in a3))
print("a4=%s" % ":".join("%02x" % x for x in a4))

# 888e
idx = pkt.find(b"\x88\x8e")
print("888e at offset %d" % idx)
eapol = pkt[idx+2:]
print("EAPOL (%d bytes):" % len(eapol))
print("Full hex:")
print(eapol.hex())
