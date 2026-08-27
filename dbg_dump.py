import struct, sys
d = open(sys.argv[1], "rb").read()
o = "<" if d[:4] == b"\xd4\xc3\xb2\xa1" else ">"
off = 24
count = 0
eapol_found = 0
while off + 16 <= len(d):
    ts_sec, ts_usec, incl, orig = struct.unpack(o + "IIII", d[off:off+16])
    off += 16
    if incl == 0:
        break
    pkt = d[off:off+incl]
    off += incl
    count += 1
    # search for 888e anywhere
    idx = pkt.find(b"\x88\x8e")
    if idx != -1:
        eapol_found += 1
        print("pkt%d len=%d 888e at %d context: %s" % (count, incl, idx, pkt[max(0,idx-4):idx+20].hex()))
    if count <= 3:
        print("pkt%d len=%d first24: %s" % (count, incl, pkt[:24].hex()))
print("total:", count, "eapol:", eapol_found)
