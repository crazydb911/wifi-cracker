#!/usr/bin/env python3
"""Dump pkt001 in full hex to understand its structure."""
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
pkt = pkts[1]
print("pkt001 (%d bytes):" % len(pkt))
for j in range(0, len(pkt), 16):
    row = pkt[j:j+16]
    hexstr = " ".join("%02x" % b for b in row)
    print("  %3d: %s" % (j, hexstr))

# Parse 802.11 header
fctl = struct.unpack("<H", pkt[0:2])[0]
dur = struct.unpack("<H", pkt[2:4])[0]
a1 = pkt[4:10]
a2 = pkt[10:16]
a3 = pkt[16:22]
a4 = pkt[22:28]
print()
print("fctl=0x%04x dur=%d" % (fctl, dur))
print("a1=%s" % ":".join("%02x" % x for x in a1))
print("a2=%s" % ":".join("%02x" % x for x in a2))
print("a3=%s" % ":".join("%02x" % x for x in a3))
print("a4=%s" % ":".join("%02x" % x for x in a4))

# Find 888e
idx = pkt.find(b"\x88\x8e")
print("888e at offset %d" % idx)
eapol = pkt[idx+2:]
print("eapol[0]=%02x type" % eapol[0])
print("eapol[1:3]=%s keyinfo" % eapol[1:3].hex())
print("eapol[3:5]=%s keylen" % eapol[3:5].hex())
print("eapol[5]=%d msgnum" % eapol[5])
print()
print("Full EAPOL hex:")
print(eapol.hex())
