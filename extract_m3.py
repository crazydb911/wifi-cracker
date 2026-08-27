#!/usr/bin/env python3
"""Extract full EAPOL frame from M3 for hashcat 22000 format."""
import struct

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"
AP_MAC = b"\x6c\x4f\x89\x4c\xa0\xe4"  # a3 for M1/M3
ESSID = "32H9F_5G"

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
print(f"Total packets: {len(pkts)}")

# Find M3 frames (msg=3, a3=AP_MAC)
m3_frames = []
for i, pkt in enumerate(pkts):
    if len(pkt) < 50: continue
    # 802.11 header: fctl(2) dur(2) a1(6) a2(6) a3(6) = 22 bytes
    a3 = pkt[16:22]
    if a3 != AP_MAC: continue
    # LLC/SNAP at offset 28
    if pkt[28:30] != b'\x88\x8e': continue
    # EAPOL at offset 30
    eapol = pkt[30:]
    if len(eapol) < 6: continue
    msgnum = eapol[5]
    if msgnum == 3:
        m3_frames.append((i, pkt, eapol))
        print(f"M3 frame {i}: len={len(eapol)}, eapol_hex={h(eapol[:50])}...")

print(f"\nTotal M3 frames: {len(m3_frames)}")

# Extract the first M3 frame's full EAPOL
if m3_frames:
    idx, pkt, eapol = m3_frames[0]
    print(f"\nFirst M3 frame (pkt {idx}):")
    print(f"  Full EAPOL hex ({len(eapol)} bytes): {h(eapol)}")
    
    # Parse EAPOL header
    # type(1) keyinfo(2) keylen(2) msgnum(1)
    etype = eapol[0]
    keyinfo = struct.unpack(">H", eapol[1:3])[0]
    keylen = struct.unpack(">H", eapol[3:5])[0]
    msgnum = eapol[5]
    print(f"  type={etype}, keyinfo=0x{keyinfo:04x}, keylen={keylen}, msgnum={msgnum}")
    
    # Body starts at eapol[6]
    body = eapol[6:]
    print(f"  Body length: {len(body)} bytes")
    print(f"  Body first 50 bytes: {h(body[:50])}")
    
    # M3 body: anonce(32) + snonce(32) + [mic(16) + keydata]
    anonce = body[:32]
    snonce = body[32:64]
    rest = body[64:]
    print(f"  ANonce: {h(anonce)}")
    print(f"  SNonce: {h(snonce)}")
    print(f"  Rest: {len(rest)} bytes")
    
    # Build hashcat 22000 EAPOL hash
    # Format: WPA*02*<keymic32>*<apmac12>*<stamac12>*<essid_hex>*<anonce64>*<eapol_full>*<msgpair>
    
    # keymic = 32 hex chars (16 bytes) - from M3 body[64:80] if present
    if len(rest) >= 16:
        keymic = h(rest[:16])
    else:
        keymic = "0" * 32
    
    # apmac = 12 hex chars (6 bytes)
    apmac = h(AP_MAC)
    
    # stamac = 12 hex chars (6 bytes) - from a1 field
    sta_mac = pkt[4:10]
    stamac = h(sta_mac)
    
    # essid_hex = hex of SSID
    essid_hex = ESSID.encode().hex()
    
    # anonce = 64 hex chars (32 bytes)
    anonce_hex = h(anonce)
    
    # eapol_full = hex of entire EAPOL frame
    eapol_hex = h(eapol)
    
    # msgpair = 011 (M2+M3, EAPOL from M3)
    msgpair = "03"
    
    hash_line = f"WPA*02*{keymic}*{apmac}*{stamac}*{essid_hex}*{anonce_hex}*{eapol_hex}*{msgpair}"
    print(f"\n  Hashcat 22000 hash:")
    print(f"  {hash_line}")
    
    # Write to file
    out = r"C:\Users\crazydb911\Documents\deepseek\hashes\32h9f_22000_eapol"
    with open(out, "w") as f:
        f.write(hash_line + "\n")
    print(f"\n  Written to {out}")
