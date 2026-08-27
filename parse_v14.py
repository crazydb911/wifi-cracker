#!/usr/bin/env python3
"""V14: find M2 (msgnum=2) packets for target BSSID and extract snonce."""
import struct

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"
TARGET_BSSID = b"\x6c\x4f\x89\x4c\xa0\xe4"

def mac(b): return ":".join("%02x" % x for x in b)
def h(b): return b.hex()

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

m2_count = 0
for i, pkt in enumerate(pkts):
    idx = pkt.find(b"\x88\x8e")
    if idx == -1: continue
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    msg = eapol[5]
    a1 = pkt[4:10]
    a3 = pkt[16:22]
    
    if msg == 2:
        m2_count += 1
        a2 = pkt[10:16]
        # M2: STA->AP, so a1=STA, a2=AP
        print("pkt%03d M2 a1=%s a2=%s a3=%s" % (i, mac(a1), mac(a2), mac(a3)))
        # M2 body: snonce(32) keydatalen(2) keydata(...)
        o = 6
        snonce = eapol[o:o+32]; o += 32
        print("  snonce: %s" % h(snonce))
        # Check if there's more data
        if o < len(eapol):
            kdlen = struct.unpack(">H", eapol[o:o+2])[0]
            print("  keydatalen: %d" % kdlen)
            if kdlen > 0 and o + 2 + kdlen <= len(eapol):
                print("  keydata: %s" % h(eapol[o+2:o+2+kdlen]))
        print()

print("Total M2 packets: %d" % m2_count)
