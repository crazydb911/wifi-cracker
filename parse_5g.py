#!/usr/bin/env python3
"""Parse 32h9f_eapol.pcapng with correct 802.11 header (28 bytes).
   Header: fctl(2) dur(2) a1(6) a2(6) a3(6) a4(6) = 28 bytes
   Then LLC/SNAP: 88 8e (2 bytes), then EAPOL.
   
   EAPOL: type(1) keyinfo(2) keylen(2) msgnum(1)
   M1: anonce(32) addr(6) ssid(32)
   M2: anonce(32) snonce(32)
   M3: anonce(32) snonce(32) addr(6) ssid(32) mic(16)
   M4: anonce(32) snonce(32) addr(6) ssid(32) mic(16)
"""
import struct

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"
TARGET_BSSID = "6c:4f:89:4c:a0:e4"

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
    # 802.11 header is 28 bytes, then 888e (2 bytes), then EAPOL
    # So EAPOL starts at offset 30
    m1 = m2 = m3 = m4 = 0
    target_frames = []
    for i, pkt in enumerate(pkts):
        # Verify 888e at offset 28
        if pkt[28:30] != b"\x88\x8e":
            # Try to find 888e
            idx = pkt.find(b"\x88\x8e")
            if idx == -1:
                continue
            eapol = pkt[idx+2:]
        else:
            eapol = pkt[30:]
        
        if len(eapol) < 6 or eapol[0] != 1:
            continue
        msg = eapol[5]
        # 802.11 addresses
        a1 = pkt[4:10]   # dst
        a2 = pkt[10:16]  # src
        a3 = pkt[16:22]  # bssid
        a4 = pkt[22:28]  # 4th addr
        
        o = 6
        if msg == 1:
            m1 += 1
            anonce = eapol[o:o+32]; o += 32
            apaddr = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            print("pkt%03d M1 a1=%s a2=%s a3=%s a4=%s ssid=%r anonce=%s" % (
                i, mac(a1), mac(a2), mac(a3), mac(a4),
                ssid.rstrip(b"\x00").decode("utf-8","replace"), h(anonce)))
        elif msg == 2:
            m2 += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            print("pkt%03d M2 a1=%s a2=%s a3=%s a4=%s anonce=%s snonce=%s" % (
                i, mac(a1), mac(a2), mac(a3), mac(a4), h(anonce), h(snonce)))
        elif msg == 3:
            m3 += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            apaddr = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            print("pkt%03d M3 a1=%s a2=%s anonce=%s snonce=%s mic=%s" % (
                i, mac(a1), mac(a2), h(anonce), h(snonce), h(mic)))
        elif msg == 4:
            m4 += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            apaddr = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            print("pkt%03d M4 a1=%s a2=%s mic=%s" % (i, mac(a1), mac(a2), h(mic)))
        else:
            print("pkt%03d: unknown msg=%d" % (i, msg))
    print("M1=%d M2=%d M3=%d M4=%d" % (m1, m2, m3, m4))

if __name__ == "__main__":
    main()
