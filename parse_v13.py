#!/usr/bin/env python3
"""V13: check ALL keyinfo values across all packets."""
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

keyinfo_counts = {}
for i, pkt in enumerate(pkts):
    idx = pkt.find(b"\x88\x8e")
    if idx == -1: continue
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    keyinfo = eapol[1:3].hex()
    keyinfo_counts[keyinfo] = keyinfo_counts.get(keyinfo, 0) + 1

print("keyinfo values across all packets:")
for k, v in sorted(keyinfo_counts.items()):
    ki = struct.unpack(">H", bytes.fromhex(k))[0]
    r = (ki >> 15) & 1
    secure = (ki >> 14) & 1
    install = (ki >> 13) & 1
    keyack = (ki >> 12) & 1
    keymic = (ki >> 11) & 1
    keydata = (ki >> 10) & 1
    print("  %s: %d packets (R=%d Sec=%d Inst=%d Ack=%d MIC=%d Data=%d)" % (
        k, v, r, secure, install, keyack, keymic, keydata))
