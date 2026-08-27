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

for i in (2, 3, 6, 17):
    pkt = pkts[i]
    print("pkt%02d (%d bytes):" % (i, len(pkt)))
    for j in range(0, len(pkt), 16):
        row = pkt[j:j+16]
        hexstr = " ".join("%02x" % b for b in row)
        print("  %3d: %s" % (j, hexstr))
    print()
