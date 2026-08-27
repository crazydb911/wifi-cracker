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
print("total:", len(pkts))
for i in range(min(12, len(pkts))):
    pkt = pkts[i]
    idx = pkt.find(b"\x88\x8e")
    eapol = pkt[idx+2:idx+60] if idx != -1 else b""
    print("pkt%03d len=%d 888e@%d eapol[:30]=%s" % (i, len(pkt), idx, eapol[:30].hex()))
# also check last packet
for i in range(max(0, len(pkts)-3), len(pkts)):
    pkt = pkts[i]
    idx = pkt.find(b"\x88\x8e")
    eapol = pkt[idx+2:idx+60] if idx != -1 else b""
    print("pkt%03d len=%d 888e@%d eapol[:30]=%s" % (i, len(pkt), idx, eapol[:30].hex()))
