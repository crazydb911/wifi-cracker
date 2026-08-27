#!/usr/bin/env python3
"""V8: scan all packets for a valid 16-byte MIC (no 8 leading zeros)."""
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
print("packets:", len(pkts))

for i, pkt in enumerate(pkts):
    idx = pkt.find(b"\x88\x8e")
    if idx == -1: continue
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    msg = eapol[5]
    a3 = pkt[16:22]
    if a3 != b"\x6c\x4f\x89\x4c\xa0\xe4": continue
    
    if msg == 3:
        o = 6
        anonce = eapol[o:o+32]; o += 32
        snonce = eapol[o:o+32]; o += 32
        # Scan for MIC: look for 16 bytes that don't start with 8+ zeros
        for start in range(o, min(o+10, len(eapol)-16)):
            candidate = eapol[start:start+16]
            # Check if candidate has non-zero bytes in first 8 positions
            if any(b != 0 for b in candidate[:8]):
                print("pkt%03d M3 MIC at +%d: %s" % (i, start-o, candidate.hex()))
                break
        else:
            print("pkt%03d M3 no valid MIC found" % i)
