import struct
d = open(r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng", "rb").read()
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
print("pkts:", len(pkts))
for i in (0, 3, 5):
    pkt = pkts[i]
    print("pkt%02d first 40 bytes: %s" % (i, pkt[:40].hex()))
    idx = pkt.find(b"\x88\x8e")
    print("  888e at", idx)
    eapol = pkt[idx+2:idx+64]
    print("  eapol[:32]: %s" % eapol[:32].hex())
