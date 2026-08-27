#!/usr/bin/env python3
"""V6: CORRECT EAPOL parser.
   
   802.11 header: fctl(2) dur(2) a1(6) a2(6) a3(6) a4(6) = 28 bytes
   LLC/SNAP: 88 8e = 2 bytes
   EAPOL starts at offset 30:
     type(1)=01  keyinfo(2)  keylen(2)  msgnum(1)
   
   M1 body: anonce(32) apaddr(6) ssid(32) mic(16) keydatalen(2) keydata(...)
   M3 body: anonce(32) snonce(32) mic(16) keydatalen(2) keydata(...)
   
   keyinfo bits (big-endian 16-bit):
     [15]=R [14]=Secure [13]=Install [12]=KeyAck
     [11]=KeyMIC [10]=KeyData [9:0]=reserved
   
   keylen = length of Key Data field (NOT the key itself)
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

best_m1 = None
best_m3 = None
m1_count = m3_count = 0

for i, pkt in enumerate(pkts):
    idx = pkt.find(b"\x88\x8e")
    if idx == -1: continue
    eapol = pkt[idx+2:]
    if len(eapol) < 6 or eapol[0] != 1: continue
    msg = eapol[5]
    
    # 802.11 addresses (fixed positions in 28-byte header)
    a1 = pkt[4:10]
    a2 = pkt[10:16]
    a3 = pkt[16:22]
    a4 = pkt[22:28]
    
    if msg == 1 and a3 == TARGET_BSSID:
        m1_count += 1
        o = 6
        anonce = eapol[o:o+32]; o += 32
        apaddr = eapol[o:o+6]; o += 6
        ssid = eapol[o:o+32]; o += 32
        mic = eapol[o:o+16]; o += 16
        # Verify anonce is not all zeros
        if anonce != b"\x00"*32:
            if best_m1 is None:
                best_m1 = (i, anonce, a1, a3)
    
    elif msg == 3 and a3 == TARGET_BSSID:
        m3_count += 1
        o = 6
        anonce = eapol[o:o+32]; o += 32
        snonce = eapol[o:o+32]; o += 32
        mic = eapol[o:o+16]; o += 16
        # STA is a1 (dst) for M3 (STA->AP, AP is dst)
        if anonce != b"\x00"*32:
            if best_m3 is None:
                best_m3 = (i, anonce, snonce, mic, a1)

print("M1(target)=%d M3(target)=%d" % (m1_count, m3_count))

if best_m1 and best_m3:
    idx1, anonce1, sta1, ap1 = best_m1
    idx3, anonce3, snonce3, mic3, sta3 = best_m3
    
    print()
    print("=== M1 (pkt%03d) ===" % idx1)
    print("ANonce: %s" % h(anonce1))
    print("STA: %s" % mac(sta1))
    print()
    print("=== M3 (pkt%03d) ===" % idx3)
    print("ANonce: %s" % h(anonce3))
    print("SNonce: %s" % h(snonce3))
    print("MIC: %s" % h(mic3))
    print("STA(a1): %s" % mac(sta3))
    print()
    
    # Use M3's anonce (should match M1's)
    anonce = anonce3
    snonce = snonce3
    mic = mic3
    sta = sta1  # from M1 (dst = STA)
    
    print("=== Final hash data ===")
    print("ESSID: %s" % ESSID)
    print("AP MAC: %s" % mac(TARGET_BSSID))
    print("STA MAC: %s" % mac(sta))
    print("ANonce: %s" % h(anonce))
    print("SNonce: %s" % h(snonce))
    print("KeyMic: %s" % h(mic))
    
    # hashcat 22000: ESSID:AP:STA:ANonce:SNonce:KeyMicAP:KeyMicSTA:EKeyAP:EKeySTA
    hash_line = "%s:%s:%s:%s:%s:%s:%s:%s:%s" % (
        ESSID, mac(TARGET_BSSID), mac(sta), h(anonce), h(snonce), h(mic),
        "00000000000000000000000000000000",
        "00000000000000000000000000000000",
        "00000000000000000000000000000000"
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
