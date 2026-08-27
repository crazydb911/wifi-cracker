#!/usr/bin/env python3
"""Dump pkt000 M1 with byte annotations."""
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
idx = pkt.find(b"\x88\x8e")
eapol = pkt[idx+2:]

print("pkt000 M1 EAPOL (%d bytes):" % len(eapol))
print()
print("type (0-1):   %s" % eapol[0:1].hex())
print("keyinfo (1-3): %s" % eapol[1:3].hex())
print("keylen (3-5):  %s (%d)" % (eapol[3:5].hex(), struct.unpack(">H", eapol[3:5])[0]))
print("msgnum (5-6):  %d" % eapol[5])
print()
print("anonce (6-38):  %s" % eapol[6:38].hex())
print("apaddr (38-44): %s" % ":".join("%02x" % x for x in eapol[38:44]))
print("ssid   (44-76): %r" % eapol[44:76].rstrip(b"\x00").decode("utf-8","replace"))
print("mic    (76-92): %s" % eapol[76:92].hex())
print()
print("Remaining after mic: %d bytes" % (len(eapol) - 92))
print("  %s" % eapol[92:].hex())
