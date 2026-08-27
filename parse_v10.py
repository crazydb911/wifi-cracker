#!/usr/bin/env python3
"""V10: verify M1 data (anonce, apaddr, ssid, mic) for all M1 packets."""
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
print("packets:", len(pkts))

for i, pkt in enumerate(pkts):
    idx = pkt.find(b"\x88\x8e")
    if idx == -1: continue
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    msg = eapol[5]
    a1 = pkt[4:10]
    a3 = pkt[16:22]
    if msg == 1 and a3 == TARGET_BSSID:
        o = 6
        anonce = eapol[o:o+32]; o += 32
        apaddr = eapol[o:o+6]; o += 6
        ssid = eapol[o:o+32]; o += 32
        mic = eapol[o:o+16]; o += 16
        # Check if MIC is all zeros
        mic_zero = all(b == 0 for b in mic[:8])
        print("pkt%03d M1 anonce=%s apaddr=%s ssid=%r mic=%s (leading_zeros=%s)" % (
            i, h(anonce)[:16]+"...", mac(apaddr), 
            ssid.rstrip(b"\x00").decode("utf-8","replace"),
            h(mic), mic_zero))
