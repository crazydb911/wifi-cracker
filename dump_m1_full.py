#!/usr/bin/env python3
"""Dump pkt000 (M1) EAPOL in full to understand the structure."""
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
print("pkt000 EAPOL (%d bytes):" % len(eapol))
for i in range(0, len(eapol), 16):
    row = eapol[i:i+16]
    print("  %3d: %s" % (i, " ".join("%02x" % b for b in row)))
print()
print("eapol[0]=%d type" % eapol[0])
print("eapol[1:3]=%s keyinfo" % eapol[1:3].hex())
print("eapol[3:5]=%s keylen=%d" % (eapol[3:5].hex(), struct.unpack(">H", eapol[3:5])[0]))
print("eapol[5]=%d msgnum" % eapol[5])
print("eapol[6]=%d reserved" % eapol[6])
print()
# M1 body starts at offset 7
o = 7
print("M1 body:")
anonce = eapol[o:o+32]; o += 32
print("anonce(32)=%s" % anonce.hex())
addr = eapol[o:o+6]; o += 6
print("addr(6)=%s" % ":".join("%02x" % x for x in addr))
ssid = eapol[o:o+32]; o += 32
print("ssid(32)=%r" % ssid.rstrip(b"\x00"))
print("remaining bytes: %d" % (len(eapol) - o))
if len(eapol) >= o + 2:
    kdlen = struct.unpack(">H", eapol[o:o+2])[0]
    print("keydatalen(2)=%d" % kdlen)
    o += 2
    if kdlen > 0 and len(eapol) >= o + kdlen:
        keydata = eapol[o:o+kdlen]
        print("keydata(%d)=%s" % (kdlen, keydata.hex()))
