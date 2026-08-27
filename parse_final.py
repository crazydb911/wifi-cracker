#!/usr/bin/env python3
"""Final EAPOL parser for 32h9f_eapol.pcapng.
   
   802.11 header: fctl(2) dur(2) a1(6) a2(6) a3(6) [a4(6)] = 22 or 28 bytes
   Then LLC/SNAP: 88 8e (2 bytes)
   Then EAPOL: type(1) keyinfo(2) keylen(2) msgnum(1) body...
   
   M1: anonce(32) addr(6) ssid(32)
   M2: anonce(32) snonce(32)
   M3: anonce(32) snonce(32) addr(6) ssid(32) mic(16)
   M4: anonce(32) snonce(32) addr(6) ssid(32) mic(16)
   
   Target: BSSID = 6c:4f:89:4c:a0:e4
"""
import struct

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"
TARGET_BSSID = b"\x6c\x4f\x89\x4c\xa0\xe4"

def mac(b):
    return ":".join("%02x" % x for x in b)

def h(b):
    return b.hex()

def read_pkts(path):
    d = open(path, "rb").read()
    pkts = []
    off = 0
    n = len(d)
    while off + 8 <= n:
        blktype = struct.unpack("<I", d[off:off+4])[0]
        blklen = struct.unpack("<I", d[off+4:off+8])[0]
        if blklen < 12 or off + blklen > n:
            break
        if blktype == 0x00000006:
            body = d[off+8:off+blklen-4]
            pkts.append(body[4:])
        off += blklen
    return pkts

def main():
    pkts = read_pkts(PATH)
    print("packets:", len(pkts))
    m1 = m2 = m3 = m4 = other = 0
    target_m1 = None
    target_m3 = None
    target_m4 = None
    
    for i, pkt in enumerate(pkts):
        # Find 888e
        idx = pkt.find(b"\x88\x8e")
        if idx == -1:
            other += 1
            continue
        eapol = pkt[idx+2:]
        if len(eapol) < 6 or eapol[0] != 1:
            other += 1
            continue
        msg = eapol[5]
        # Get 802.11 addresses (they're at fixed positions in the header)
        a1 = pkt[4:10]   # dst
        a2 = pkt[10:16]  # src
        a3 = pkt[16:22]  # bssid
        
        o = 6
        if msg == 1:
            m1 += 1
            anonce = eapol[o:o+32]; o += 32
            apaddr = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            if a3 == TARGET_BSSID:
                target_m1 = (i, anonce, apaddr, ssid, a1)
                print("pkt%03d M1 TARGET a1=%s anonce=%s" % (i, mac(a1), h(anonce)))
        elif msg == 2:
            m2 += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            print("pkt%03d M2 a1=%s a2=%s a3=%s anonce=%s snonce=%s" % (
                i, mac(a1), mac(a2), mac(a3), h(anonce), h(snonce)))
        elif msg == 3:
            m3 += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            apaddr = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            if a3 == TARGET_BSSID or a1 == TARGET_BSSID or a2 == TARGET_BSSID:
                target_m3 = (i, anonce, snonce, mic, a1, a2, a3)
                print("pkt%03d M3 TARGET a1=%s a2=%s a3=%s anonce=%s snonce=%s mic=%s" % (
                    i, mac(a1), mac(a2), mac(a3), h(anonce), h(snonce), h(mic)))
        elif msg == 4:
            m4 += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            apaddr = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            print("pkt%03d M4 a1=%s a2=%s mic=%s" % (i, mac(a1), mac(a2), h(mic)))
        else:
            other += 1
    
    print()
    print("M1=%d M2=%d M3=%d M4=%d other=%d" % (m1, m2, m3, m4, other))
    
    # Build hashcat 22000 hash from M3 (which has all the data we need)
    if target_m1 and target_m3:
        idx1, anonce1, apaddr1, ssid1, a1_1 = target_m1
        idx3, anonce3, snonce3, mic3, a1_3, a2_3, a3_3 = target_m3
        # hashcat 22000 format:
        # ESSID:AP MAC:STA MAC:ANonce:SNonce:KeyMic AP:KeyMic STA:EKey AP:EKey STA
        # M3 has: anonce, snonce, mic (this is the Key MIC)
        # ESSID = "32H9F_5G" (from the task)
        essid = "32H9F_5G"
        ap_mac = mac(TARGET_BSSID)
        sta_mac = mac(a1_3)  # the station
        anonce = h(anonce3)  # AP nonce (from M3, same as M1)
        snonce = h(snonce3)  # STA nonce
        key_mic_ap = h(mic3)  # Key MIC from M3 (sent by STA, verifies AP's M1)
        # M4 has KeyMic STA and EKeys - but we don't have M4
        # For hashcat 22000, we need both M3 and M4
        # Without M4, we can use aircrack-ng format or hcxpcapngtool
        print()
        print("=== M3 data (for hash) ===")
        print("ESSID: %s" % essid)
        print("AP MAC: %s" % ap_mac)
        print("STA MAC: %s" % sta_mac)
        print("ANonce: %s" % anonce)
        print("SNonce: %s" % snonce)
        print("KeyMic: %s" % key_mic_ap)
        print()
        # Write hashcat 22000 hash (incomplete without M4, but useful)
        # Format: ESSID:AP MAC:STA MAC:ANonce:SNonce:KeyMic AP:KeyMic STA:EKey AP:EKey STA
        # Without M4: use zeros for KeyMic STA and EKeys
        hash_line = "%s:%s:%s:%s:%s:%s:%s:%s:%s" % (
            essid, ap_mac, sta_mac, anonce, snonce, key_mic_ap, 
            "00000000000000000000000000000000",  # KeyMic STA (from M4, missing)
            "00000000000000000000000000000000",  # EKey AP (from M4, missing)
            "00000000000000000000000000000000"   # EKey STA (from M4, missing)
        )
        print("hashcat 22000 hash (incomplete, no M4):")
        print(hash_line)
        
        # Also write aircrack-ng format (ESSID:AP:STA:WPA:ANonce:SNonce:KeyMic:KeyMic STA:EKey AP:EKey STA)
        # Actually aircrack-ng uses its own format
        import os
        hashdir = r"C:\Users\crazydb911\Documents\deepseek\hashes"
        if not os.path.exists(hashdir):
            os.makedirs(hashdir)
        hashfile = os.path.join(hashdir, "32h9f.22000")
        with open(hashfile, "w") as f:
            f.write(hash_line + "\n")
        print()
        print("Wrote %s" % hashfile)
    elif target_m3:
        idx3, anonce3, snonce3, mic3, a1_3, a2_3, a3_3 = target_m3
        essid = "32H9F_5G"
        ap_mac = mac(TARGET_BSSID)
        sta_mac = mac(a1_3)
        anonce = h(anonce3)
        snonce = h(snonce3)
        key_mic = h(mic3)
        print()
        print("=== M3 data ===")
        print("ESSID: %s" % essid)
        print("AP MAC: %s" % ap_mac)
        print("STA MAC: %s" % sta_mac)
        print("ANonce: %s" % anonce)
        print("SNonce: %s" % snonce)
        print("KeyMic: %s" % key_mic)

if __name__ == "__main__":
    main()
