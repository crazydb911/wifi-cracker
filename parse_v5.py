#!/usr/bin/env python3
"""V5: parse EAPOL with correct keylen interpretation.
   
   EAPOL header: type(1) keyinfo(2) keylen(2) msgnum(1)
   keyinfo bits: [15]=R, [14]=Secure, [13]=Install, [12]=KeyAck, [11]=Key MIC, [10]=Key Data, [9:0]=reserved
   
   For M1: keyinfo=0x0300, keylen=0x0075(117), msgnum=1
   M1 body: anonce(32) addr(6) ssid(32) = 70 bytes
   But keylen=117, so keydata = 117-70 = 47 bytes
   
   For M3: keyinfo=0x0300, keylen=0x005F(95), msgnum=3
   M3 body: anonce(32) snonce(32) = 64 bytes
   But keylen=95, so keydata = 95-64 = 31 bytes
   
   Wait, keylen in 802.11i is the length of the Key Data field (which includes everything after the EAPOL header).
   Actually, re-reading the spec: Key Length field is 2 bytes, indicating the length of the Key Data field.
   The Key Data field starts after the MIC (16 bytes) and Key Data Length (2 bytes).
   
   Let me re-examine. The EAPOL-Key frame format is:
   Protocol Version (2) | Type (1) | Key Info (2) | Key Length (2) | Message Number (1) | Reserved (1)
   [Key Data (Key Length bytes)]
   [Key RSC (32) - if Secure bit set]
   [Key Replay Counter (8) - if Key MIC bit set]
   [Key ID (64) - if Key MIC bit set]
   [Key MIC (16) - if Key MIC bit set]
   [Key Data Length (2) + Key Data - if Key Data bit set]
   
   Wait, that's not right either. Let me look at the actual structure more carefully.
   
   From IEEE 802.11i-2004, Figure 8-14:
   EAPOL-Key frame:
   - Protocol Version (1 byte)
   - Type (1 byte) = 0x03
   - Key Information (2 bytes)
   - Key Length (2 bytes) - length of the Key Data field (NOT the key itself)
   - Message Number (1 byte)
   - Reserved (1 byte)
   - Key Data (Key Length bytes)
   - Key RSC (32 bytes, if Secure bit)
   - Key Replay Counter (8 bytes, if Key MIC bit)
   - Key ID (64 bytes, if Key MIC bit)
   - Key MIC (16 bytes, if Key MIC bit)
   - Key Data Length (2 bytes) + Key Data (if Key Data bit)
   
   Hmm, that doesn't match what I'm seeing. Let me just parse it empirically.
   
   For M1 (pkt000):
   eapol = 01 03 00 75 01 00 [32 bytes anonce] [6 bytes addr] [32 bytes ssid] ...
   type=01, keyinfo=0300, keylen=0075=117, msgnum=01
   After msgnum: 00 0a 00 00 ... (32 bytes) = anonce
   Then: f1 f1 59 2c 44 06 (6 bytes) = addr
   Then: 20 a1 50 a7 ff 00 ... (32 bytes) = ssid
   Total so far: 1+2+2+1+1+32+6+32 = 77 bytes
   keylen=117, so 117-77 = 40 more bytes
   
   For M3 (pkt002):
   eapol = 01 03 00 5f 03 00 [32 bytes anonce] [32 bytes snonce] ...
   type=01, keyinfo=0300, keylen=005f=95, msgnum=03
   After msgnum: 00 0a 00 00 ... (32 bytes) = anonce
   Then: f1 f1 59 2c ... (32 bytes) = snonce
   Total so far: 1+2+2+1+1+32+32 = 71 bytes
   keylen=95, so 95-71 = 24 more bytes
   
   The 24 bytes after snonce in M3 would be: [16 bytes MIC] + [2 bytes keydata length] + [6 bytes ?]
   But I extracted mic = 000000000000000000000018c03399b6 from the 16 bytes after snonce,
   which is mostly zeros with some data at the end. That doesn't look like a proper MIC.
   
   Let me dump more of pkt002 to see what comes after the snonce.
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

# Dump pkt002 (M3) EAPOL in full
pkt = pkts[2]
idx = pkt.find(b"\x88\x8e")
eapol = pkt[idx+2:]
print("pkt002 EAPOL (%d bytes):" % len(eapol))
print(eapol.hex())
print()
# Show byte-by-byte
for i in range(0, min(120, len(eapol)), 16):
    row = eapol[i:i+16]
    print("  %3d: %s" % (i, " ".join("%02x" % b for b in row)))
