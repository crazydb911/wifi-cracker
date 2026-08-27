#!/usr/bin/env python3
"""V7: dump all bytes after snonce in M3 to find the real MIC."""
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
print("Full hex:")
print(eapol.hex())
print()
# EAPOL header
print("type=%d keyinfo=%s keylen=%d msgnum=%d" % (
    eapol[0], eapol[1:3].hex(), struct.unpack(">H", eapol[3:5])[0], eapol[5]))
print()
# M3 body
o = 6
anonce = eapol[o:o+32]; o += 32
print("anonce(32)=%s" % anonce.hex())
snonce = eapol[o:o+32]; o += 32
print("snonce(32)=%s" % snonce.hex())
print()
print("After snonce (offset %d), remaining %d bytes:" % (o, len(eapol)-o))
print("  %s" % eapol[o:].hex())
print()
# Try different MIC positions
for start in range(o, min(o+10, len(eapol)-16)):
    candidate = eapol[start:start+16]
    print("  MIC at +%d: %s" % (start-o, candidate.hex()))
