#!/usr/bin/env python3
"""Accurate EAPOL analysis with correct msg numbering."""
import struct

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"

def h(b): return b.hex()
def mac(b): return ":".join("%02x" % x for x in b)

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
print(f"Total packets: {len(pkts)}")

# Correct EAPOL msg numbering:
# eapol[5] = 1 -> M1 (AP -> STA)
# eapol[5] = 2 -> M2 (STA -> AP)  
# eapol[5] = 3 -> M3 (AP -> STA)
# eapol[5] = 4 -> M4 (STA -> AP)

m1_valid = []
m2_valid = []
m3_valid = []
m4_valid = []

for i, pkt in enumerate(pkts):
    if len(pkt) < 50: continue
    idx = pkt.find(b'\x88\x8e')
    if idx == -1: continue
    
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    
    msgnum = eapol[5]
    a1 = pkt[4:10]
    a2 = pkt[10:16]
    a3 = pkt[16:22]
    body = eapol[6:]
    
    if msgnum == 1:  # M1
        anonce = body[:32] if len(body) >= 32 else b''
        if anonce and anonce != b'\x00'*32:
            m1_valid.append((i, a1, a3, anonce))
    elif msgnum == 2:  # M2
        snonce = body[:32] if len(body) >= 32 else b''
        if snonce and snonce != b'\x00'*32:
            m2_valid.append((i, a1, a3, snonce))
    elif msgnum == 3:  # M3
        anonce = body[:32] if len(body) >= 32 else b''
        snonce = body[32:64] if len(body) >= 64 else b''
        mic = body[64:80] if len(body) >= 80 else b''
        m3_valid.append((i, a1, a3, anonce, snonce, mic))
    elif msgnum == 4:  # M4
        mic = body[:16] if len(body) >= 16 else b''
        m4_valid.append((i, a1, a3, mic))

print(f"\nM1 frames with valid ANonce: {len(m1_valid)}")
print(f"M2 frames with valid SNonce: {len(m2_valid)}")
print(f"M3 frames: {len(m3_valid)}")
print(f"M4 frames: {len(m4_valid)}")

# Check M3 frames
print("\n=== M3 Frame Details ===")
for i, a1, a3, anonce, snonce, mic in m3_valid[:5]:
    print(f"\nFrame {i}:")
    print(f"  a1={mac(a1)} a3={mac(a3)}")
    print(f"  ANonce: {h(anonce)}")
    print(f"  SNonce: {h(snonce)}")
    print(f"  MIC: {h(mic)}")
    print(f"  ??  SNonce is {'all zeros' if snonce == b'\x00'*32 else 'valid'}")

# Check if we can use M2+M4 (msgpair=0)
print("\n=== M2 Frames (first 5) ===")
for i, a1, a3, snonce in m2_valid[:5]:
    print(f"\nFrame {i}:")
    print(f"  a1={mac(a1)} a3={mac(a3)}")
    print(f"  SNonce: {h(snonce)}")
