import struct, sys
d = open("/volume1/homes/crazydb911/wifi-cracker-32h9f/captures/5g_v2.pcap", "rb").read()
o = "<"
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
    if count == 28:  # pkt index 27
        print("pkt27 full hex:")
        print(pkt.hex())
        print()
        # Search for 888e
        idx = pkt.find(b"\x88\x8e")
        print("888e at:", idx)
        # Try different offsets
        for tryoff in range(max(0, idx-4), idx+4):
            body = pkt[tryoff:]
            if len(body) >= 5:
                etype = body[0]
                ki = struct.unpack(">H", body[1:3])[0]
                kl = struct.unpack(">H", body[3:5])[0]
                mn = (ki >> 12) & 0x3
                print("  tryoff=%d: type=%d keyinfo=0x%04x msgnum=%d keylen=%d" % (
                    tryoff, etype, ki, mn, kl))
        break
