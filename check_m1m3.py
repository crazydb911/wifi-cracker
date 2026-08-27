#!/usr/bin/env python3
"""Check M1-M3 pairing for valid handshake."""
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

# Collect all M1 and M3 frames
m1_frames = []
m3_frames = []

for i, pkt in enumerate(pkts):
    if len(pkt) < 50: continue
    idx = pkt.find(b'\x88\x8e')
    if idx == -1: continue
    
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    
    msgnum = eapol[5]
    a1 = pkt[4:10]
    a3 = pkt[16:22]
    body = eapol[6:]
    
    if msgnum == 1:  # M1
        anonce = body[:32] if len(body) >= 32 else b''
        if anonce and anonce != b'\x00'*32:
            m1_frames.append((i, a1, a3, anonce))
    elif msgnum == 3:  # M3
        anonce = body[:32] if len(body) >= 32 else b''
        snonce = body[32:64] if len(body) >= 64 else b''
        mic = body[64:80] if len(body) >= 80 else b''
        if anonce and anonce != b'\x00'*32 and snonce and snonce != b'\x00'*32:
            m3_frames.append((i, a1, a3, anonce, snonce, mic))

print(f"Valid M1 frames: {len(m1_frames)}")
print(f"Valid M3 frames: {len(m3_frames)}")

# Check if M1 and M3 have matching ANonce
print("\n=== Checking M1-M3 ANonce matches ===")
for i1, a1_1, a3_1, anonce1 in m1_frames:
    for i3, a1_3, a3_3, anonce3, snonce3, mic3 in m3_frames:
        if anonce1 == anonce3:
            print(f"\n? MATCH: M1 frame {i1} and M3 frame {i3}")
            print(f"  M1: a1={mac(a1_1)} a3={mac(a3_1)}")
            print(f"  M3: a1={mac(a1_3)} a3={mac(a3_3)}")
            print(f"  ANonce: {h(anonce1)}")
            print(f"  SNonce: {h(snonce3)}")
            print(f"  MIC: {h(mic3)}")
