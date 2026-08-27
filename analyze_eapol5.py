#!/usr/bin/env python3
"""Parse 32h9f_eapol.pcapng properly:
   802.11 data frame: fctl(2) dur(2) a1(6) a2(6) a3(6) [seq(2)] LLC(3) SNAP(3) [EAPOL]
   EAPOL: type(1)=1, keyinfo(2), keylen(2), msgnum(1), anonce(32), snonce(32),
          addr(6), ssid(32), mic(16), keydata(2+keydata_len).
   msgnum is at eapol offset 5 (0-based: eapol[5]).
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
    counts = {1:0, 2:0, 3:0, 4:0, 0:0}
    for i, pkt in enumerate(pkts):
        # find 888e
        idx = pkt.find(b"\x88\x8e")
        if idx == -1:
            counts[0] += 1
            continue
        eapol = pkt[idx+2:]
        if len(eapol) < 6:
            counts[0] += 1
            continue
        # EAPOL header: type(1), keyinfo(2), keylen(2), msgnum(1)
        etype = eapol[0]
        if etype != 1:
            counts[0] += 1
            continue
        keyinfo = struct.unpack(">H", eapol[1:3])[0]
        keylen = struct.unpack(">H", eapol[3:5])[0]
        msg = eapol[5]
        dst = mac(pkt[2:8])   # a1
        src = mac(pkt[8:14])  # a2
        bssid = mac(pkt[14:20])  # a3
        o = 6  # skip type, keyinfo, keylen, msgnum
        if msg == 1:
            counts[1] += 1
            anonce = eapol[o:o+32]; o += 32
            apaddr = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            print("pkt%03d M1 ap=%s sta=%s ssid=%r anonce=%s" % (
                i, mac(apaddr), dst,
                ssid.rstrip(b"\x00").decode("utf-8","replace"),
                h(anonce)))
        elif msg == 2:
            counts[2] += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            print("pkt%03d M2 sta=%s anonce=%s snonce=%s" % (i, dst, h(anonce), h(snonce)))
        elif msg == 3:
            counts[3] += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            apaddr = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            kdlen = struct.unpack(">H", eapol[o:o+2])[0]; o += 2
            keydata = eapol[o:o+kdlen]
            print("pkt%03d M3 sta=%s mic=%s keydata=%s" % (i, dst, h(mic), h(keydata)))
        elif msg == 4:
            counts[4] += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            apaddr = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            kdlen = struct.unpack(">H", eapol[o:o+2])[0]; o += 2
            keydata = eapol[o:o+kdlen]
            print("pkt%03d M4 ap=%s mic=%s keydata=%s" % (i, mac(apaddr), h(mic), h(keydata)))
        else:
            counts[0] += 1
    print("M1=%d M2=%d M3=%d M4=%d other=%d" % (counts[1],counts[2],counts[3],counts[4],counts[0]))

if __name__ == "__main__":
    main()
