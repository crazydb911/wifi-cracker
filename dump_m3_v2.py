#!/usr/bin/env python3
"""Dump pkt002 EAPOL with byte-by-byte offset annotation."""
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
idx = pkt.find(b"\x88\x8e")
eapol = pkt[idx+2:]
print("pkt002 EAPOL (%d bytes):" % len(eapol))
print()
# Byte-by-byte with annotations
labels = []
labels.append(("type", 0, 1))
labels.append(("keyinfo", 1, 3))
labels.append(("keylen", 3, 5))
labels.append(("msgnum", 5, 6))
labels.append(("anonce", 6, 38))
labels.append(("snonce", 38, 70))
labels.append(("mic?", 70, 86))
labels.append(("rest", 86, len(eapol)))

for name, start, end in labels:
    chunk = eapol[start:end]
    print("%s (%d-%d): %s" % (name, start, end, chunk.hex()))
    print()
