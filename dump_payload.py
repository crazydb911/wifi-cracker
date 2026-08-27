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
pkt = pkts[0]
print("len:", len(pkt))
print("full hex:")
print(pkt.hex())
idx = pkt.find(b"\x88\x8e")
print("888e at", idx)
# 802.11 header: fctl(2) dur(2) a1(6) a2(6) a3(6) seq(2) = 24 bytes
print("fctl:", hex(struct.unpack("<H", pkt[0:2])[0]))
print("a1:", pkt[2:8].hex())
print("a2:", pkt[8:14].hex())
print("a3:", pkt[14:20].hex())
print("seq:", pkt[20:22].hex())
print("payload[24:40]:", pkt[24:40].hex())
print("payload[26:42]:", pkt[26:42].hex())
