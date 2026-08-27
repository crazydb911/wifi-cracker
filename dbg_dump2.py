import struct, sys
d = open(sys.argv[1], "rb").read()
o = "<" if d[:4] == b"\xd4\xc3\xb2\xa1" else ">"
off = 24
count = 0
while off + 16 <= len(d):
    ts_sec, ts_usec, incl, orig = struct.unpack(o + "IIII", d[off:off+16])
    off += 16
    if incl == 0:
        break
    pkt = d[off:off+incl]
    off += incl
    count += 1
    if count in (28, 35, 40, 42):
        print("pkt%d len=%d full: %s" % (count, incl, pkt.hex()))
        print()
