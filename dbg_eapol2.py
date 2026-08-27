import struct, sys
sys.path.insert(0, "/volume1/homes/crazydb911/wifi-cracker-32h9f/scripts")
import wpa2_extract as w
pkts, lt = w.read_pcap(sys.argv[1])
print("pkts:", len(pkts), "lt:", lt)
# Test pkt27 specifically (index 27 = 28th packet)
pkt = pkts[27]
print("pkt27 len:", len(pkt))
print("pkt27 first 30 bytes hex:", pkt[:30].hex())
print("ethertype at 12:14:", hex(struct.unpack(">H", pkt[12:14])[0]))
print("find 888e:", pkt.find(b"\x88\x8e"))
print("find_eapol:", w.find_eapol(pkt, lt))
print("find_eapol_80211:", w.find_eapol_80211(pkt))
