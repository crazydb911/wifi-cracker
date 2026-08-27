import sys
sys.path.insert(0, "/volume1/homes/crazydb911/wifi-cracker-32h9f/scripts")
import importlib
import wpa2_extract as w
importlib.reload(w)
pkts, lt = w.read_pcap("/volume1/homes/crazydb911/wifi-cracker-32h9f/captures/5g_v2.pcap")
pkt = pkts[27]
fe = w.find_eapol(pkt, lt)
eapol, src, dst = fe
print("eapol first 10:", eapol[:10].hex())
p = w.parse_eapol(eapol)
print("parse:", p)
