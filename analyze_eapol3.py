#!/usr/bin/env python3
"""Parse 32h9f_eapol.pcapng: frames are 802.11 data (no seq/ack), EAPOL at 26."""
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
    m1 = m2 = m3 = m4 = 0
    for i, pkt in enumerate(pkts):
        idx = pkt.find(b"\x88\x8e")
        if idx == -1:
            print("pkt%03d: no 888e, first bytes %s" % (i, pkt[:10].hex()))
            continue
        eapol = pkt[idx+2:]
        if len(eapol) < 5 or eapol[0] != 1:
            print("pkt%03d: bad eapol type=%d" % (i, eapol[0] if eapol else -1))
            continue
        keyinfo = struct.unpack(">H", eapol[1:3])[0]
        msg = (keyinfo >> 12) & 0x3
        keylen = struct.unpack(">H", eapol[3:5])[0]
        dst = mac(pkt[2:8])
        src = mac(pkt[8:14])
        bssid = mac(pkt[14:20])
        o = 5
        if msg == 1:
            m1 += 1
            anonce = eapol[o:o+32]; o += 32
            ab = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            print("pkt%03d M1 ap=%s sta=%s ssid=%r anonce=%s" % (
                i, mac(ab), dst, ssid.rstrip(b"\x00").decode("utf-8","replace"), h(anonce)))
        elif msg == 2:
            m2 += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            print("pkt%03d M2 ap=%s sta=%s anonce=%s snonce=%s" % (
                i, bssid, dst, h(anonce), h(snonce)))
        elif msg == 3:
            m3 += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            ab = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            kdlen = struct.unpack(">H", eapol[o:o+2])[0]; o += 2
            keydata = eapol[o:o+kdlen]
            print("pkt%03d M3 sta=%s mic=%s keydata=%s" % (i, dst, h(mic), h(keydata)))
        elif msg == 4:
            m4 += 1
            anonce = eapol[o:o+32]; o += 32
            snonce = eapol[o:o+32]; o += 32
            ab = eapol[o:o+6]; o += 6
            ssid = eapol[o:o+32]; o += 32
            mic = eapol[o:o+16]; o += 16
            kdlen = struct.unpack(">H", eapol[o:o+2])[0]; o += 2
            keydata = eapol[o:o+kdlen]
            print("pkt%03d M4 ap=%s mic=%s keydata=%s" % (i, mac(ab), h(mic), h(keydata)))
        else:
            print("pkt%03d: unknown msg=%d" % (i, msg))
    print("counts: M1=%d M2=%d M3=%d M4=%d" % (m1, m2, m3, m4))

if __name__ == "__main__":
    main()
