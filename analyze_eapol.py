#!/usr/bin/env python3
"""Detailed EAPOL frame analysis for 32h9f_eapol.pcapng"""
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

eapol_count = 0
msg_counts = {0:0, 1:0, 2:0, 3:0}

for i, pkt in enumerate(pkts):
    if len(pkt) < 50: continue
    # Find LLC/SNAP 88 8e
    idx = pkt.find(b'\x88\x8e')
    if idx == -1: continue
    
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    
    eapol_count += 1
    msgnum = eapol[5]
    if msgnum in msg_counts:
        msg_counts[msgnum] += 1
    
    # Parse header
    keyinfo = struct.unpack(">H", eapol[1:3])[0]
    keylen = struct.unpack(">H", eapol[3:5])[0]
    keyver = keyinfo & 3
    
    # 802.11 addresses
    a1 = pkt[4:10]
    a2 = pkt[10:16]
    a3 = pkt[16:22]
    
    print(f"\nFrame {i}: msg={msgnum}, keyinfo=0x{keyinfo:04x}, keylen={keylen}, keyver={keyver}")
    print(f"  a1={mac(a1)} a2={mac(a2)} a3={mac(a3)}")
    print(f"  EAPOL length: {len(eapol)} bytes")
    
    # Body
    body = eapol[6:]
    if len(body) >= 32:
        anonce = body[:32]
        print(f"  ANonce: {h(anonce)}")
        if anonce == b'\x00'*32:
            print(f"  ??  ANonce is all zeros!")
    
    if msgnum == 0:  # M2
        if len(body) >= 64:
            snonce = body[32:64]
            print(f"  SNonce: {h(snonce)}")
            if snonce == b'\x00'*32:
                print(f"  ??  SNonce is all zeros!")
            if len(body) >= 80:
                mic = body[64:80]
                print(f"  MIC: {h(mic)}")
                if mic == b'\x00'*16:
                    print(f"  ??  MIC is all zeros!")
    elif msgnum == 3:  # M3
        if len(body) >= 64:
            snonce = body[32:64]
            print(f"  SNonce: {h(snonce)}")
            if snonce == b'\x00'*32:
                print(f"  ??  SNonce is all zeros!")
            if len(body) >= 80:
                mic = body[64:80]
                print(f"  MIC: {h(mic)}")
                if mic == b'\x00'*16:
                    print(f"  ??  MIC is all zeros!")

print(f"\n\nSummary: {eapol_count} EAPOL frames")
print(f"  M1 (msg=1): {msg_counts[1]}")
print(f"  M2 (msg=0): {msg_counts[0]}")
print(f"  M3 (msg=2): {msg_counts[2]}")
print(f"  M4 (msg=3): {msg_counts[3]}")
