import struct

eapol = b'\x88\x8e\x01\x03\x00\x5f\x02\x00\x8a\x00'
print("len:", len(eapol))
print("eapol[0]:", eapol[0], "eapol[1]:", eapol[1])
print("starts 888e:", eapol[0] == 0x88 and eapol[1] == 0x8e)
if eapol[0] == 0x88 and eapol[1] == 0x8e:
    eapol = eapol[2:]
print("after skip:", eapol.hex())
print("len after skip:", len(eapol))
if len(eapol) < 5:
    print("too short")
else:
    eapol_type = eapol[0]
    print("eapol_type:", eapol_type)
    if eapol_type != 0:
        print("wrong type")
    key_info = struct.unpack(">H", eapol[1:3])[0]
    print("key_info: 0x%04x" % key_info)
    print("msg_num:", (key_info >> 12) & 0x3)
    key_len = struct.unpack(">H", eapol[3:5])[0]
    print("key_len:", key_len)
