#!/usr/bin/env python3
"""Correct EAPOL parser.
   The capture is a tshark 802.11 dump (linktype 105).
   Each frame: 802.11 header (fctl(2) dur(2) a1(6) a2(6) a3(6)) = 24 bytes,
   then LLC/SNAP (888e0003aa), then EAPOL.
   
   EAPOL structure (802.11i):
   type(1) keyinfo(2) keylen(2) msgnum(1)
   Then body depends on msgnum:
   M1: anonce(32) addr(6) ssid(32) mic(16) keydata_len(2) keydata
   M2: anonce(32) snonce(32) mic(16) keydata_len(2) keydata
   M3: anonce(32) snonce(32) addr(6) ssid(32) mic(16) keydata_len(2) keydata
   M4: anonce(32) snonce(32) addr(6) ssid(32) mic(16) keydata_len(2) keydata
"""
import struct

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"

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
    counts = {0:0, 1:0, 2:0, 3:0, 4:0}
    for i, pkt in enumerate(pkts):
        idx = pkt.find(b"\x88\x8e")
        if idx == -1:
            counts[0] += 1
            continue
        eapol = pkt[idx+2:]
        if len(eapol) < 6:
            counts[0] += 1
            continue
        etype = eapol[0]
        if etype != 1:
            counts[0] += 1
            continue
        msg = eapol[5]
        # 802.11 addresses (from the 802.11 header, before 888e)
        # idx points to 888e in pkt; 802.11 header is pkt[0:24]
        a1 = pkt[2:8]   # dst
        a2 = pkt[8:14]  # src
        a3 = pkt[14:20] # bssid
        o = 6
        if msg == 1:
            counts[1] += 1
            anonce = eapol[o:o+32]; o += 32
            apaddr = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            kdlen = struct.unpack(">H", eapol[o:o+2])[0] if o+2 <= len(eapol) else 0; o += 2
            keydata = eapol[o:o+kdlen]
            print("pkt%03d M1 ap=%s sta=%s ssid=%r anonce=%s" % (
                i, mac(apaddr), mac(a1),
                ssid.rstrip(b"\x00").decode("utf-8","replace"),
                h(anonce)))
        elif msg == 2:
            counts[2] += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            kdlen = struct.unpack(">H", eapol[o:o+2])[0] if o+2 <= len(eapol) else 0; o += 2
            keydata = eapol[o:o+kdlen]
            print("pkt%03d M2 sta=%s anonce=%s snonce=%s" % (i, mac(a1), h(anonce), h(snonce)))
        elif msg == 3:
            counts[3] += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            apaddr = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            kdlen = struct.unpack(">H", eapol[o:o+2])[0] if o+2 <= len(eapol) else 0; o += 2
            keydata = eapol[o:o+kdlen]
            print("pkt%03d M3 sta=%s anonce=%s snonce=%s mic=%s" % (
                i, mac(a1), h(anonce), h(snonce), h(mic)))
        elif msg == 4:
            counts[4] += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            apaddr = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            kdlen = struct.unpack(">H", eapol[o:o+2])[0] if o+2 <= len(eapol) else 0; o += 2
            keydata = eapol[o:o+kdlen]
            print("pkt%03d M4 ap=%s mic=%s keydata=%s" % (i, mac(apaddr), h(mic), h(keydata)))
        else:
            counts[0] += 1
    print("M1=%d M2=%d M3=%d M4=%d other=%d" % (counts[1],counts[2],counts[3],counts[4],counts[0]))

if __name__ == "__main__":
    main()
