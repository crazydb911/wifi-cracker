#!/usr/bin/env python3
"""V12: check if keylen is little-endian and find the real MIC."""
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

# Check M1 and M3 keylen as LE and BE
for i, pkt in enumerate(pkts[:10]):
    idx = pkt.find(b"\x88\x8e")
    if idx == -1: continue
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    msg = eapol[5]
    a3 = pkt[16:22]
    if a3 != b"\x6c\x4f\x89\x4c\xa0\xe4": continue
    
    keyinfo = eapol[1:3]
    keylen_be = struct.unpack(">H", eapol[3:5])[0]
    keylen_le = struct.unpack("<H", eapol[3:5])[0]
    
    # Parse keyinfo bits
    ki = struct.unpack(">H", keyinfo)[0]
    r = (ki >> 15) & 1
    secure = (ki >> 14) & 1
    install = (ki >> 13) & 1
    keyack = (ki >> 12) & 1
    keymic = (ki >> 11) & 1
    keydata = (ki >> 10) & 1
    
    print("pkt%03d M%d keyinfo=%s R=%d Sec=%d Inst=%d Ack=%d MIC=%d Data=%d keylen_BE=%d keylen_LE=%d" % (
        i, msg, keyinfo.hex(), r, secure, install, keyack, keymic, keydata, keylen_be, keylen_le))
