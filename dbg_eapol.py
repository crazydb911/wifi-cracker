import struct, sys
sys.path.insert(0, "/volume1/homes/crazydb911/wifi-cracker-32h9f/scripts")
from wpa2_extract import read_pcap, find_eapol, parse_eapol
pkts, lt = read_pcap(sys.argv[1])
print("pkts:", len(pkts), "lt:", lt)
for i, pkt in enumerate(pkts):
    fe = find_eapol(pkt, lt)
    if fe:
        eapol, src, dst = fe
        p = parse_eapol(eapol)
        print("pkt%d: eapol len=%d src=%s dst=%s msg=%s keylen=%s nonce=%s mic=%s" % (
            i, len(eapol), src.hex(), dst.hex(),
            p["msg_num"] if p else None,
            p["key_len"] if p else None,
            (p["nonce"] or b"")[:8].hex() if p else None,
            (p["mic"] or b"")[:8].hex() if p else None,
        ))
    else:
        if i < 30:
            print("pkt%d: no eapol, len=%d first8=%s" % (i, len(pkt), pkt[:8].hex()))
