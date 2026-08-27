#!/usr/bin/env python3
"""Dump a msg=0 packet in full."""
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
pkt = pkts[1]  # pkt001 is msg=0
print("pkt001 (%d bytes):" % len(pkt))
for i in range(0, len(pkt), 16):
    row = pkt[i:i+16]
    print("  %3d: %s" % (i, " ".join("%02x" % b for b in row)))

print()
idx = pkt.find(b"\x88\x8e")
eapol = pkt[idx+2:]
print("EAPOL (%d bytes):" % len(eapol))
print("Full hex:")
print(eapol.hex())
print()
print("type=%d keyinfo=%s keylen_BE=%d keylen_LE=%d msgnum=%d" % (
    eapol[0], eapol[1:3].hex(), 
    struct.unpack(">H", eapol[3:5])[0],
    struct.unpack("<H", eapol[3:5])[0],
    eapol[5]))
print()
# M2 body: snonce(32) keydatalen(2) keydata(...)
o = 6
snonce = eapol[o:o+32]; o += 32
print("snonce(32)=%s" % snonce.hex())
kdlen_be = struct.unpack(">H", eapol[o:o+2])[0]
kdlen_le = struct.unpack("<H", eapol[o:o+2])[0]
print("keydatalen_BE=%d keydatalen_LE=%d" % (kdlen_be, kdlen_le))
