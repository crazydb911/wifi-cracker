import sys, struct
sys.path.insert(0, "/volume1/homes/crazydb911/wifi-cracker-32h9f/scripts")
import wpa2_extract as w

pkts, lt = w.read_pcap("/volume1/homes/crazydb911/wifi-cracker-32h9f/captures/5g_v2.pcap")
print("pkts:", len(pkts), "lt:", lt)

target = bytes.fromhex("6c4f894ca0e4")
per_sta = {}
eapol_count = 0
for i, pkt in enumerate(pkts):
    fe = w.find_eapol(pkt, lt)
    if not fe:
        continue
    eapol_count += 1
    eapol, dst, src = fe
    p = w.parse_eapol(eapol)
    if not p:
        print("pkt%d: eapol found but parse failed" % i)
        continue
    mn = p["msg_num"]
    if mn not in (1, 2, 3, 4):
        print("pkt%d: msg_num=%d (not 1-4)" % (i, mn))
        continue
    sta = dst if mn in (1, 3) else src
    ap = src if mn in (1, 3) else dst
    print("pkt%d: msg=%d src=%s dst=%s sta=%s ap=%s nonce=%s" % (
        i, mn, src.hex(), dst.hex(), sta.hex(), ap.hex(),
        (p["nonce"] or b"")[:8].hex()))
    rec = per_sta.setdefault(bytes(sta), {"ap": None, "ap_nonce": None, "sta_nonce": None, "ap_mic": None, "sta_mic": None, "msgs": set()})
    if mn in (1, 3):
        rec["ap"] = ap
        rec["ap_nonce"] = p["nonce"]
        if mn == 3:
            rec["ap_mic"] = p["mic"]
    else:
        rec["sta_nonce"] = p["nonce"]
        if mn == 4:
            rec["sta_mic"] = p["mic"]
    rec["msgs"].add(mn)

print("\neapol_count:", eapol_count)
print("stations:", len(per_sta))
for sta, rec in per_sta.items():
    print("  sta=%s ap=%s msgs=%s ap_nonce=%s sta_nonce=%s" % (
        sta.hex(), (rec["ap"] or b"").hex(), sorted(rec["msgs"]),
        (rec["ap_nonce"] or b"").hex()[:16], (rec["sta_nonce"] or b"").hex()[:16]))
