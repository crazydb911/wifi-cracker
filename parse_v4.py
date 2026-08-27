#!/usr/bin/env python3
"""V4: use M3's own anonce (matches M1) for the hash.
   M3's anonce is the AP's nonce (same value as in M1).
"""
import struct, os

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"
TARGET_BSSID = b"\x6c\x4f\x89\x4c\xa0\xe4"
ESSID = "32H9F_5G"

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

# Find the best M1 (for STA MAC) and best M3 (for anonce/snonce/mic)
best_m1 = None
best_m3 = None

for i, pkt in enumerate(pkts):
    idx = pkt.find(b"\x88\x8e")
    if idx == -1: continue
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    msg = eapol[5]
    a1 = pkt[4:10]
    a2 = pkt[10:16]
    a3 = pkt[16:22]
    a4 = pkt[22:28]
    o = 6
    
    if msg == 1 and a3 == TARGET_BSSID:
        anonce = eapol[o:o+32]; o += 32
        apaddr = eapol[o:o+6]; o += 6
        if anonce != b"\x00"*32 and best_m1 is None:
            best_m1 = (i, anonce, a1)  # a1 = STA (dst)
    
    elif msg == 3 and a3 == TARGET_BSSID:
        anonce = eapol[o:o+32]; o += 32
        snonce = eapol[o:o+32]; o += 32
        mic = eapol[o:o+16]; o += 16
        if anonce != b"\x00"*32 and best_m3 is None:
            best_m3 = (i, anonce, snonce, mic)

if best_m1 and best_m3:
    idx1, anonce1, sta1 = best_m1
    idx3, anonce3, snonce3, mic3 = best_m3
    
    # Use M3's anonce (should match M1's)
    anonce = anonce3  # AP nonce from M3
    snonce = snonce3  # STA nonce from M3
    mic = mic3        # Key MIC from M3
    sta = sta1        # STA MAC from M1
    
    print("=== Handshake data ===")
    print("ESSID: %s" % ESSID)
    print("AP MAC: %s" % mac(TARGET_BSSID))
    print("STA MAC: %s" % mac(sta))
    print("ANonce: %s" % h(anonce))
    print("SNonce: %s" % h(snonce))
    print("KeyMic: %s" % h(mic))
    
    # hashcat 22000: ESSID:AP:STA:ANonce:SNonce:KeyMicAP:KeyMicSTA:EKeyAP:EKeySTA
    hash_line = "%s:%s:%s:%s:%s:%s:%s:%s:%s" % (
        ESSID, mac(TARGET_BSSID), mac(sta), h(anonce), h(snonce), h(mic),
        "00000000000000000000000000000000",  # KeyMic STA (M4, missing)
        "00000000000000000000000000000000",  # EKey AP (M4, missing)
        "00000000000000000000000000000000"   # EKey STA (M4, missing)
    )
    print()
    print("hashcat 22000 hash:")
    print(hash_line)
    
    hashdir = r"C:\Users\crazydb911\Documents\deepseek\hashes"
    if not os.path.exists(hashdir): os.makedirs(hashdir)
    hashfile = os.path.join(hashdir, "32h9f.22000")
    with open(hashfile, "w") as f:
        f.write(hash_line + "\n")
    print("Wrote %s" % hashfile)
    
    # Also write aircrack-ng compatible format
    # aircrack-ng: ESSID:AP MAC:STA MAC:WPA:ANonce:SNonce:KeyMic:KeyMic STA:EKey AP:EKey STA
    # Actually aircrack-ng uses its own .cap file format, not this text format
    # For hashcat, the above format is correct for mode 22000
