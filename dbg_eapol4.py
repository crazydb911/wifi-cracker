import sys
sys.path.insert(0, "/volume1/homes/crazydb911/wifi-cracker-32h9f/scripts")
import wpa2_extract as w
pkts, lt = w.read_pcap("/volume1/homes/crazydb911/wifi-cracker-32h9f/captures/5g_v2.pcap")
pkt = pkts[27]
fe = w.find_eapol(pkt, lt)
eapol, src, dst = fe
print("eapol first 10:", eapol[:10].hex())
print("eapol type:", eapol[0])
import struct
key_info = struct.unpack(">H", eapol[1:3])[0]
print("key_info: 0x%04x" % key_info)
print("msg_num:", (key_info >> 12) & 0x3)
key_len = struct.unpack(">H", eapol[3:5])[0]
print("key_len:", key_len)
print("keymic_bit:", bool(key_info & 0x0040))
print("keyinstall_bit:", bool(key_info & 0x0002))
p = w.parse_eapol(eapol)
print("parse:", p)
