#!/usr/bin/env python3
"""Dump pkt000 (M1) with correct EAPOL layout.
   EAPOL: type(1) keyinfo(2) keylen(2) msgnum(1) [reserved(1)]
   M1 body: anonce(32) apaddr(6) ssid(32) mic(16) keydatalen(2) keydata(...)
"""
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

# EAPOL header
print("type=%d" % eapol[0])
print("keyinfo=%s" % eapol[1:3].hex())
print("keylen=%d" % struct.unpack(">H", eapol[3:5])[0])
print("msgnum=%d" % eapol[5])
print("reserved=%s" % eapol[6:7].hex())
print()

# M1 body starts at offset 7
o = 7
anonce = eapol[o:o+32]; o += 32
print("anonce(32)=%s" % anonce.hex())
apaddr = eapol[o:o+6]; o += 6
print("apaddr(6)=%s" % ":".join("%02x" % x for x in apaddr))
ssid = eapol[o:o+32]; o += 32
print("ssid(32)=%r" % ssid.rstrip(b"\x00").decode("utf-8","replace"))
mic = eapol[o:o+16]; o += 16
print("mic(16)=%s" % mic.hex())
kdlen = struct.unpack(">H", eapol[o:o+2])[0]; o += 2
print("keydatalen(2)=%d" % kdlen)
if kdlen > 0 and o + kdlen <= len(eapol):
    keydata = eapol[o:o+kdlen]
    print("keydata(%d)=%s" % (kdlen, keydata.hex()))
print()
print("Total consumed: %d of %d bytes" % (o, len(eapol)))
