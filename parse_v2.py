#!/usr/bin/env python3
"""V2 EAPOL parser.
   
   Key insight: the 802.11 header has 4 addresses (28 bytes total):
   fctl(2) dur(2) a1(6) a2(6) a3(6) a4(6)
   
   M1 (AP->STA): a1=STA, a2=AP, a3=BSSID, a4=STA
   M3 (STA->AP): a1=AP, a2=STA, a3=BSSID (or a4=STA)
   
   EAPOL: type(1) keyinfo(2) keylen(2) msgnum(1)
   M1: anonce(32) addr(6) ssid(32)
   M2: anonce(32) snonce(32)
   M3: anonce(32) snonce(32) addr(6) ssid(32) mic(16)
   M4: anonce(32) snonce(32) addr(6) ssid(32) mic(16)
   
   The 'addr' field in M3 is the AP address (not BSSID from header).
   The 'ssid' field in M3 is actually the MIC (16 bytes) + padding.
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
    
    for i, pkt in enumerate(pkts):
        idx = pkt.find(b"\x88\x8e")
        if idx == -1:
            other += 1
            continue
        eapol = pkt[idx+2:]
        if len(eapol) < 6 or eapol[0] != 1:
            other += 1
            continue
        msg = eapol[5]
        
        # 802.11 header: fctl(2) dur(2) a1(6) a2(6) a3(6) a4(6) = 28 bytes
        a1 = pkt[4:10]
        a2 = pkt[10:16]
        a3 = pkt[16:22]
        a4 = pkt[22:28]
        
        o = 6
        if msg == 1:
            m1 += 1
            anonce = eapol[o:o+32]; o += 32
            addr_field = eapol[o:o+6]; o += 6  # This is the AP address
            ssid = eapol[o:o+32]; o += 32
            # For M1, the addr field should be the AP MAC
            # The BSSID is a3 in the header
            if a3 == TARGET_BSSID:
                target_m1 = (i, anonce, addr_field, a1, a3)
                print("pkt%03d M1 a1=%s a2=%s a3=%s a4=%s apaddr=%s anonce=%s" % (
                    i, mac(a1), mac(a2), mac(a3), mac(a4), mac(addr_field), h(anonce)))
        elif msg == 2:
            m2 += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            print("pkt%03d M2 a1=%s a2=%s anonce=%s snonce=%s" % (
                i, mac(a1), mac(a2), h(anonce), h(snonce)))
        elif msg == 3:
            m3 += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            addr_field = eapol[o:o+6]; o += 6  # AP address
            # For M3, after addr comes the MIC (16 bytes), not a 32-byte SSID
            # But the spec says M3 has: anonce, snonce, addr, ssid, mic
            # Let me check: if addr is 6 bytes, then the next 16 bytes should be MIC
            # But in the hex, after addr we see: 20 a1 50 a7 ff 00 00 00 ... (32 bytes)
            # This looks like it could be a 32-byte field (SSID?) followed by MIC
            # Actually, for M3 the spec says:
            # Key Data field: ANonce(32) + SNonce(32) + AP Addr(6) + SSID(32) + Key MIC(16)
            # So the 32-byte field after addr IS the SSID, and the 16-byte field after is MIC
            ssid_field = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            # The 'ssid' field in M3 might actually be the SSID or might be zeros
            # The MIC is the 16 bytes after
            is_target = (a3 == TARGET_BSSID or a1 == TARGET_BSSID or a2 == TARGET_BSSID or a4 == TARGET_BSSID)
            if is_target:
                if target_m3 is None:
                    target_m3 = (i, anonce, snonce, mic, a1, a2, a3, a4)
                print("pkt%03d M3 a1=%s a2=%s a3=%s a4=%s apaddr=%s ssid=%r mic=%s" % (
                    i, mac(a1), mac(a2), mac(a3), mac(a4), mac(addr_field),
                    ssid_field.rstrip(b"\x00").decode("utf-8","replace"), h(mic)))
        elif msg == 4:
            m4 += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            addr_field = eapol[o:o+6]; o += 6
            ssid_field = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            print("pkt%03d M4 a1=%s a2=%s mic=%s" % (i, mac(a1), mac(a2), h(mic)))
        else:
            other += 1
    
    print()
    print("M1=%d M2=%d M3=%d M4=%d other=%d" % (m1, m2, m3, m4, other))
    
    # Use the first valid M3 (pkt002) which has real non-zero anonce/snonce/mic
    if target_m3:
        idx, anonce, snonce, mic, a1, a2, a3, a4 = target_m3
        essid = "32H9F_5G"
        ap_mac = mac(TARGET_BSSID)
        sta_mac = mac(a2)  # a2 is the STA (src) in M3
        print()
        print("=== M3 data (pkt%03d) ===" % idx)
        print("ESSID: %s" % essid)
        print("AP MAC: %s" % ap_mac)
        print("STA MAC: %s" % sta_mac)
        print("ANonce: %s" % h(anonce))
        print("SNonce: %s" % h(snonce))
        print("KeyMic: %s" % h(mic))
        
        # Write hashcat 22000 hash
        # Format: ESSID:AP MAC:STA MAC:ANonce:SNonce:KeyMic AP:KeyMic STA:EKey AP:EKey STA
        # Without M4, KeyMic STA and EKeys are unknown (use zeros)
        hash_line = "%s:%s:%s:%s:%s:%s:%s:%s:%s" % (
            essid, ap_mac, sta_mac, h(anonce), h(snonce), h(mic),
            "00000000000000000000000000000000",
            "00000000000000000000000000000000",
            "00000000000000000000000000000000"
        )
        import os
        hashdir = r"C:\Users\crazydb911\Documents\deepseek\hashes"
        if not os.path.exists(hashdir):
            os.makedirs(hashdir)
        hashfile = os.path.join(hashdir, "32h9f.22000")
        with open(hashfile, "w") as f:
            f.write(hash_line + "\n")
        print()
        print("hashcat 22000 hash:")
        print(hash_line)
        print("Wrote %s" % hashfile)

if __name__ == "__main__":
    main()
