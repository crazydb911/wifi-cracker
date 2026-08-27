#!/usr/bin/env python3
"""Try different EAPOL layouts to find the correct one."""
import struct

PATH = r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"

def read_pkts(path):
    d = open(path, "rb").read()
    pkts = []
    off = 0
    n = len(d)
    while off + 8 <= n:
        blktype = struct.unpack("<I", d[off:off+4])[0]
        blklen = struct.unpack("<I", d[off+4:off+8])[0]
        if blklen < 12 or off + blklen > n: break
        if blktype == 0x00000006:
            body = d[off+8:off+blklen-4]
            pkts.append(body[4:])
        off += blklen
    return pkts

pkts = read_pkts(PATH)
pkt = pkts[2]
idx = pkt.find(b"\x88\x8e")
eapol = pkt[idx+2:]

print("Trying different EAPOL layouts:")
print()

# Layout A: type(1) keyinfo(2) keylen(2) msgnum(1) [body at 6]
# anonce at 6-38, snonce at 38-70, mic at 70-86
print("Layout A: type(1) keyinfo(2) keylen(2) msgnum(1) [body at 6]")
print("  anonce: %s" % eapol[6:38].hex())
print("  snonce: %s" % eapol[38:70].hex())
print("  mic:    %s" % eapol[70:86].hex())
print()

# Layout B: type(1) keyinfo(2) keylen(2) msgnum(1) [reserved(1)] [body at 7]
# anonce at 7-39, snonce at 39-71, mic at 71-87
print("Layout B: type(1) keyinfo(2) keylen(2) msgnum(1) reserved(1) [body at 7]")
print("  anonce: %s" % eapol[7:39].hex())
print("  snonce: %s" % eapol[39:71].hex())
print("  mic:    %s" % eapol[71:87].hex())
print()

# Layout C: type(1) keyinfo(2) keylen(2) msgnum(1) [body at 6]
# But keylen is actually at a different position
# What if keyinfo is only 1 byte?
print("Layout C: type(1) keyinfo(1) keylen(2) msgnum(1) [body at 5]")
print("  keyinfo: %02x" % eapol[1])
print("  keylen:  %d" % struct.unpack(">H", eapol[2:4])[0])
print("  msgnum:  %d" % eapol[4])
print("  anonce:  %s" % eapol[5:37].hex())
print("  snonce:  %s" % eapol[37:69].hex())
print("  mic:     %s" % eapol[69:85].hex())
print()

# Layout D: What if the EAPOL starts at a different offset?
# What if 888e is not the right marker?
# Let me check: the 802.11 header is 28 bytes, so EAPOL should start at 28+2=30
# But what if the LLC/SNAP is different?
print("Layout D: Check if EAPOL starts at different offsets")
for start in range(26, 34):
    chunk = pkt[start:start+10]
    print("  pkt[%d:%d]=%s" % (start, start+10, chunk.hex()))
