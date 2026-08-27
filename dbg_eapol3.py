import struct, sys
sys.path.insert(0, "/volume1/homes/crazydb911/wifi-cracker-32h9f/scripts")
import wpa2_extract as w
pkts, lt = w.read_pcap(sys.argv[1])
print("pkts:", len(pkts), "lt:", lt)
for i, pkt in enumerate(pkts):
    fe = w.find_eapol(pkt, lt)
    if not fe:
        continue
    eapol, src, dst = fe
    print("pkt%d: src=%s dst=%s eapol_len=%d" % (i, src.hex(), dst.hex(), len(eapol)))
    p = w.parse_eapol(eapol)
    print("  parse_eapol: %s" % (p if p else None))
    if i > 10:
        break
