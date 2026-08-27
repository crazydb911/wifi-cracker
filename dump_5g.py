import struct

def mac(b):
    return ":".join("%02x" % x for x in b)

def h(b):
    return b.hex()

# pkt 0 (M1) - 152 bytes
# 802.11 header: fctl(2) dur(2) a1(6) a2(6) a3(6) = 24 bytes
# LLC/SNAP: 88 8e 00 03 aa = 5 bytes at offset 24
# EAPOL starts at offset 24+5 = 29? But 888e is found at offset 28
# So: fctl(2) dur(2) a1(6) a2(6) a3(6) seq(2) = 26 bytes, then 888e at 26? No, it's at 28
# Let me re-examine: the raw hex starts with 8859 0600 78e2672587 00000087 0000006c4f894ca0e4 ...
# 8859 = fctl (little-endian: 0x5988)
# 0600 = dur
# 78e2672587 00 = a1 (dst) - but this looks like 6c4f894ca0e4 reversed?
# Actually in 802.11, the byte order in the capture might be reversed for MACs
# Let me check: 78e2672587 00000087 0000006c4f894ca0e4
# If a1 = 78:e2:67:25:87:00, a2 = 00:00:87:00:00:00, a3 = 6c:4f:89:4c:a0:e4
# a3 = 6c:4f:89:4c:a0:e4 = the BSSID! So the frame is from AP to station
# But a1 (dst) = 78:e2:67:25:87:00? That's odd.
# Wait, maybe the 802.11 header is: fctl(2) dur(2) a1(6) a2(6) a3(6) seq(2) = 26 bytes
# Then at offset 26 we should have LLC/SNAP
# But 888e is at offset 28, not 26
# Let me re-check: 8859 0600 78e2 6725 8700 0000 8700 0000 6c4f 894c a0e4 888e
# Offset: 0   2   4   6   8   10  12  14  16  18  20  22  24  26
# So a1 = 78:e2:67:25:87:00 (offset 4-10)
# a2 = 00:00:87:00:00:00 (offset 10-16)
# a3 = 00:00:6c:4f:89:4c (offset 16-22)
# Then offset 22-24: a0e4
# Then offset 24: 888e?? But that's only 4 bytes after a3
# This doesn't add up. Let me re-read the hex more carefully.
# 
# Full hex of pkt0 (152 bytes):
# 8859060078e2672587000000870000006c4f894ca0e460f81dad01e4888e0103007502...
# 
# Let me split:
# 8859 = fctl
# 0600 = dur
# 78e267258700 = a1? But that's 6 bytes: 78 e2 67 25 87 00
# 000087000000 = a2? 00 00 87 00 00 00
# 6c4f894ca0e4 = a3? 6c 4f 89 4c a0 e4
# 60f81dad01e4 = ??? 6 bytes
# 888e = LLC
# 
# So the 802.11 header is 2+2+6+6+6+6 = 28 bytes!
# That's fctl(2) dur(2) a1(6) a2(6) a3(6) + 6 more bytes = 28
# The extra 6 bytes (60f81dad01e4) might be... QoS control? Or a 4th address?
# Actually for 802.11 data frames with QoS, the format is:
# fctl(2) dur(2) a1(6) a2(6) a3(6) seq(2) + QoSctrl(2) = 26 bytes
# But we have 28 bytes before 888e
# 
# Wait, let me re-count:
# 8859 (2) 0600 (2) 78e267258700 (6) 000087000000 (6) 6c4f894ca0e4 (6) 60f81dad01e4 (6) 888e (2)
# = 2+2+6+6+6+6+2 = 30 bytes, 888e at offset 28
# 
# Hmm, that's 6 groups of 6 bytes. For a standard 802.11 data frame:
# a1, a2, a3, then seq(2) + ack(2) = 4 bytes, total 2+2+18+4 = 26
# But we have 28 bytes before 888e, meaning 2 extra bytes
# 
# Actually, I think the issue is that this is a QoS data frame:
# fctl(2) dur(2) a1(6) a2(6) a3(6) seq(2) QoSctrl(2) = 26 bytes
# Then LLC/SNAP at offset 26
# But 888e is at offset 28...
# 
# Let me just try: maybe the header is fctl(2) dur(2) a1(6) a2(6) a3(6) a4(6) = 28 bytes
# That would be a 4-address frame (WDS/IBSS)
# a1=78:e2:67:25:87:00, a2=00:00:87:00:00:00, a3=6c:4f:89:4c:a0:e4, a4=60:f8:1d:ad:01:e4
# 
# Actually, I think the simplest explanation: the tshark dump might have a different header format.
# Let me just use the fact that 888e is at offset 28 and parse from there.

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

# Print full hex of pkt 0 and pkt 1 (M2)
for i in (0, 1):
    pkt = pkts[i]
    print("pkt%02d (%d bytes):" % (i, len(pkt)))
    # Print in rows of 16 bytes
    for j in range(0, len(pkt), 16):
        row = pkt[j:j+16]
        hexstr = " ".join("%02x" % b for b in row)
        print("  %3d: %s" % (j, hexstr))
    print()
