#!/usr/bin/env python3
"""V3: correct M3 parsing.
   M3 body: anonce(32) snonce(32) [no addr, no ssid] mic(16) [keydatalen(2) keydata...]
   The 'addr' and 'ssid' fields only exist in M1 and M4.
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

best_m1 = None  # (anonce, ap_mac, sta_mac)
best_m3 = None  # (anonce, snonce, mic, sta_mac)
m1_count = m3_count = 0

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
    if msg == 1:
        anonce = eapol[o:o+32]; o += 32
        apaddr = eapol[o:o+6]; o += 6
        ssid = eapol[o:o+32]; o += 32
        if a3 == TARGET_BSSID:
            m1_count += 1
            # a1 is the STA (dst), a3 is BSSID
            sta = a1
            # Verify anonce is not all zeros
            if anonce != b"\x00"*32:
                if best_m1 is None:
                    best_m1 = (i, anonce, TARGET_BSSID, sta)
                    print("pkt%03d M1 anonce=%s sta=%s" % (i, h(anonce), mac(sta)))
    elif msg == 3:
        anonce = eapol[o:o+32]; o += 32
        snonce = eapol[o:o+32]; o += 32
        mic = eapol[o:o+16]; o += 16
        # STA is a2 (src) for M3 (STA->AP)
        # But a2 looks wrong (00:00:71:00:00:00)
        # Try a4 instead
        sta = a4  # 4th address field
        if (a3 == TARGET_BSSID or a1 == TARGET_BSSID) and anonce != b"\x00"*32:
            m3_count += 1
            if best_m3 is None:
                best_m3 = (i, anonce, snonce, mic, sta)
                print("pkt%03d M3 anonce=%s snonce=%s mic=%s sta(a2)=%s sta(a4)=%s" % (
                    i, h(anonce), h(snonce), h(mic), mac(a2), mac(a4)))

print("M1(target)=%d M3(target)=%d" % (m1_count, m3_count))

if best_m1 and best_m3:
    idx1, anonce1, ap1, sta1 = best_m1
    idx3, anonce3, snonce3, mic3, sta3 = best_m3
    print()
    print("=== Pair M1(pkt%03d) + M3(pkt%03d) ===" % (idx1, idx3))
    print("ESSID: %s" % ESSID)
    print("AP MAC: %s" % mac(ap1))
    print("STA MAC: %s" % mac(sta1))
    print("ANonce: %s" % h(anonce1))
    print("SNonce: %s" % h(snonce3))
    print("KeyMic (M3): %s" % h(mic3))
    
    # hashcat 22000: ESSID:AP:STA:ANonce:SNonce:KeyMicAP:KeyMicSTA:EKeyAP:EKeySTA
    # Without M4: KeyMicSTA and EKeys are zeros
    hash_line = "%s:%s:%s:%s:%s:%s:%s:%s:%s" % (
        ESSID, mac(ap1), mac(sta1), h(anonce1), h(snonce3), h(mic3),
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
    
    # Also write a hcxpcapngtool-compatible format for verification
    # hcx format: ESSID:AP MAC:STA MAC:ANonce:SNonce:KeyMic AP:KeyMic STA:EKey AP:EKey STA
    # Same as hashcat 22000
    print()
    print("Verification: hcxpcapngtool should produce the same hash from the pcapng")
