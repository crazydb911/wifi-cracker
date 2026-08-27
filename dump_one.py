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

# pkt 0: M1
pkt = pkts[0]
idx = pkt.find(b"\x88\x8e")
eapol = pkt[idx+2:]
print("pkt0 eapol len:", len(eapol))
print("eapol hex:")
print(eapol.hex())
# type(1) keyinfo(2) keylen(2) msgnum(1) = 6 bytes header
# keyinfo = 0x0300, keylen = 0x0075 = 117
# For msg 1: anonce(32) + addr(6) + ssid(32) = 70 bytes after 6-byte header
# But keylen=117, which is 70 + 16 (mic) + 31? No...
# Actually for M1: body = anonce(32)+addr(6)+ssid(32) = 70, plus mic(16) + keydata(2+0) = 88? No
# Let me re-read the spec: keylen is the length of the Key Data field, not the whole body
# Wait, actually keylen is the total length of the EAPOL-Key body after the 2-byte keylen field
# Hmm, let me just parse it step by step
print()
print("eapol[0]=%02x (type)" % eapol[0])
print("eapol[1:3]=%s (keyinfo)" % eapol[1:3].hex())
print("eapol[3:5]=%s (keylen=%d)" % (eapol[3:5].hex(), struct.unpack(">H", eapol[3:5])[0]))
print("eapol[5]=%02x (msgnum)" % eapol[5])
print()
# Body starts at offset 6
# M1: anonce(32) + addr(6) + ssid(32)
print("anonce (32):", eapol[6:38].hex())
print("addr   (6): ", eapol[38:44].hex())
print("ssid   (32):", eapol[44:76].hex(), "=%r" % eapol[44:76].rstrip(b"\x00").decode("utf-8","replace"))
print()
# After ssid: mic(16) + keydata_len(2) + keydata
print("mic    (16):", eapol[76:92].hex())
print("kdlen  (2): ", struct.unpack(">H", eapol[92:94])[0] if len(eapol) >= 94 else "N/A")
print("keydata:", eapol[94:].hex())
print()
print("total eapol len:", len(eapol))
print("expected: 6+32+6+32+16+2+0 =", 6+32+6+32+16+2+0)
