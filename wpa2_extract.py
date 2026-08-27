#!/usr/bin/env python3
"""
Extract WPA2 4-way handshake info from a pcap/pcapng capture.
Pure Python (hashlib + struct only) so it runs on the NAS (Python 3.8, no
external deps, no gcc).

Outputs a hashcat mode 22000 hash:
  <essid>:<bssid>:<eSSID-esc>:<mac-sta>:<mac-ap>:<nonce-sta>:<nonce-ap>:<keymic-sta>:<keymic-ap>:<eKey-sta>:<eKey-ap>

Usage: python3 wpa2_extract.py <capture.pcap|pcapng> [expected_bssid]
"""
import sys, struct, hashlib, re

BSSID_TARGET = "6C:4F:89:4C:A0:E4"

def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)

def read_pcap(path):
    """Return list of (pkt_bytes) from pcap or pcapng."""
    data = open(path, "rb").read()
    if data[:4] == b"\xa1\xb2\xc3\xd4" or data[:4] == b"\xd4\xc3\xb2\xa1":
        # magic 0xa1b2c3d4: a LE file stores d4c3b2a1; a BE file stores a1b2c3d4
        order = "<" if data[:4] == b"\xd4\xc3\xb2\xa1" else ">"
        print("pcap endianness: %s" % ("little" if order == "<" else "big"))
        ver_maj, ver_min = struct.unpack(order + "HH", data[4:8])
        thiszone, sigfigs, snaplen, network = struct.unpack(order + "iiII", data[8:24])
        print("pcap: network=%d snaplen=%d" % (network, snaplen))
        pkts = []
        off = 24
        while off + 16 <= len(data):
            ts_sec, ts_usec, incl, orig = struct.unpack(order + "IIII", data[off:off+16])
            off += 16
            if incl == 0 or off + incl > len(data):
                break
            pkts.append(data[off:off+incl])
            off += incl
        return pkts, network
    elif data[:4] == b"\x0a\x0d\x0d\x0a":
        return read_pcapng(data)
    else:
        die("unknown capture format, magic=%s" % data[:4].hex())

def read_pcapng(data):
    """Parse pcapng SHB + IDB + SPB blocks. Returns (pkts, linktype)."""
    pkts = []
    linktype = None
    off = 0
    n = len(data)
    while off + 8 <= n:
        blktype = struct.unpack("<I", data[off:off+4])[0]
        blklen = struct.unpack("<I", data[off+4:off+8])[0]
        if blklen < 12 or off + blklen > n:
            break
        body = data[off+8:off+blklen-4]
        if blktype == 0x0A0D0D0A:
            # Section Header Block
            pass
        elif blktype == 0x00000001:
            # Interface Description Block
            if linktype is None:
                # linktype at body offset 0, 2 bytes
                lt = struct.unpack("<H", body[0:2])[0]
                linktype = lt
        elif blktype == 0x00000006:
            # Simple Packet Block: first 4 bytes = interface id, rest = data
            pkts.append(body[4:])
        off += blklen
    return pkts, linktype

def find_eapol(pkt, linktype):
    """Find EAPOL payload in a frame. Returns (eapol_payload, src_mac, dst_mac) or None."""
    # DLT_EN10MB (1): Ethernet header. DLT_IEEE802_11 (105): 802.11 frame.
    # Some 802.11 captures are stored with linktype=1 (en10mb) but the actual
    # payload is an 802.11 frame. Detect via 0x888e search and 802.11 fctl.
    if len(pkt) >= 14:
        ethertype = struct.unpack(">H", pkt[12:14])[0]
        if ethertype != 0x888e:
            # Not a plain Ethernet EAPOL frame. Try 802.11.
            r = find_eapol_80211(pkt)
            if r:
                return r
            # Last resort: search for 0x888e anywhere and treat as EAPOL body.
            idx = pkt.find(b"\x88\x8e")
            if idx != -1:
                eapol = pkt[idx+2:]
                if len(pkt) >= 22:
                    dst = pkt[4:10]
                    src = pkt[10:16]
                    return eapol, src, dst
                return eapol, b"\x00"*6, b"\x00"*6
            return None
    else:
        return None
    # Ethernet frame: src mac at 6..12, dst 0..6, ethertype at 12..14
    if len(pkt) < 14:
        return None
    ethertype = struct.unpack(">H", pkt[12:14])[0]
    if ethertype == 0x8100 or ethertype == 0x88a8:
        # 802.1Q / 802.1ad: inner ethertype at 14..16
        ethertype = struct.unpack(">H", pkt[14:16])[0]
        base = 16
    elif ethertype == 0x88e7:
        base = 14
    else:
        base = 12
    if ethertype != 0x888e:
        return None
    if base + 5 > len(pkt):
        return None
    eapol = pkt[base:]
    dst = pkt[0:6]
    src = pkt[6:12]
    return eapol, src, dst

def find_eapol_80211(pkt):
    """Parse 802.11 frame (DLT_IEEE802_11). Find EAPOL. Returns (eapol, src_mac, dst_mac) or None."""
    if len(pkt) < 24:
        return None
    fctl = struct.unpack(">H", pkt[2:4])[0]
    ftype = fctl & 0x03
    # Management (0) / Control (1) / Data (2)
    to_ds = fctl & 0x01
    from_ds = fctl & 0x02
    # address layout:
    #   Data: toDS=0 fromDS=0: [addr1=dst][addr2=src][addr3=bssid]
    #   Data: toDS=1 fromDS=0: [addr1=dst][addr2=bssid][addr3=src] (client->AP relayed)
    #   Data: toDS=0 fromDS=1: [addr1=bssid][addr2=dst][addr3=src] (AP->client)
    #   Data: toDS=1 fromDS=1: [addr1=dst][addr2=bssid][addr3=bssid]
    #   Mgmt  (toDS=0 fromDS=0): [addr1=dst][addr2=src][addr3=bssid]
    if len(pkt) < 24 + 6:
        return None
    a1 = pkt[4:10]
    a2 = pkt[10:16]
    a3 = pkt[16:22] if len(pkt) >= 22 else None
    if ftype == 2:  # data
        if to_ds == 1 and from_ds == 0:
            dst, src, hlen = a1, a3 if a3 else a2, 18
        elif to_ds == 0 and from_ds == 1:
            dst, src, hlen = a2, a3 if a3 else a2, 18
        else:
            dst, src, hlen = a1, a2, 18
    else:  # mgmt / control
        dst, src, hlen = a1, a2, 18
    # 802.11 QoS control (2 bytes) may precede payload on data frames.
    # Search for 0x888e in payload region, trying both offsets.
    payload = pkt[hlen:]
    idx = payload.find(b"\x88\x8e")
    if idx != -1:
        eapol = payload[idx:]
    else:
        idx2 = payload[2:].find(b"\x88\x8e")
        if idx2 != -1:
            eapol = payload[2+idx2:]
        else:
            return None
    return eapol, src, dst

def parse_eapol(eapol):
    """Parse EAPOL. Return dict or None."""
    # If eapol starts with 0x888e (ethertype), skip it.
    if len(eapol) >= 2 and eapol[0:2] == b"\x88\x8e":
        eapol = eapol[2:]
    if len(eapol) < 5:
        return None
    eapol_type = eapol[0]
    if eapol_type != 0:  # EAPOL-Key (type 0)
        return None
    # Some captures have an extra 1-byte header (e.g., 0x01) before the
    # actual EAPOL body. If the first 2 bytes look like (0x01, 0x03) or
    # (0x01, 0x04), treat them as a prefix and shift.
    if eapol[1:3] in (b"\x03\x00", b"\x04\x00", b"\x02\x00", b"\x01\x00"):
        # This is likely a mis-parsed frame where the EAPOL body starts
        # at offset 1. The key_info would be eapol[1:3] as 0x0300 etc.
        # Actually: if eapol[0]=1, eapol[1:3]=0300, then key_info=0x0300
        # which is not a valid msg_num. The real EAPOL body starts at
        # eapol[1:] with type=eapol[1]=0x03? No, that's not right either.
        # Let's just check: if the first byte is 0x01 and the next 2 bytes
        # form a valid key_info (msg_num 1-4), shift.
        pass
    key_info = struct.unpack(">H", eapol[1:3])[0]
    msg_num = (key_info >> 12) & 0x3
    key_len = struct.unpack(">H", eapol[3:5])[0]
    # EAPOL-Key structure:
    #  type(1) keyinfo(2) keylen(2) nonce(32)
    #  [if keymic bit set:] key data (keylen bytes) then MIC (16)
    #  [if keyinstall bit set:] EKEY (32) + IV (16) + RSC (16) + EKEYMIC (16)
    # For hashcat 22000:
    #   msg 1 (AP->STA): keyinstall=1, keymic=0. Has AP nonce, no MIC.
    #   msg 2 (STA->AP): keymic=1. Has STA nonce + STA MIC.
    #   msg 3 (AP->STA): keymic=1. Has AP MIC.
    #   msg 4 (STA->AP): keymic=0. No MIC.
    keymic_bit = key_info & 0x0040
    keyinstall_bit = key_info & 0x0002
    off = 5
    nonce = eapol[off:off+32]; off += 32
    if keyinstall_bit:
        # EKEY (32) + IV (16) + RSC (16) + EKEYMIC (16) = 80 bytes
        off += 80
    if keymic_bit:
        # key data (keylen) then MIC (16)
        if off + keylen + 16 <= len(eapol):
            data = eapol[off:off+keylen]
            mic = eapol[off+keylen:off+keylen+16]
        else:
            data = eapol[off:off+keylen]
            mic = eapol[off+keylen:]
    else:
        data = b""
        mic = None
    return {"msg_num": msg_num, "key_len": key_len, "nonce": nonce, "mic": mic, "data": data}

def mac_hex(b):
    return ":".join("%02x" % x for x in b)

def main():
    if len(sys.argv) < 2:
        die("usage: wpa2_extract.py <capture> [expected_bssid]")
    path = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) > 2 else BSSID_TARGET
    target_b = bytes.fromhex(target.replace(":", ""))

    pkts, linktype = read_pcap(path)
    print("packets: %d  linktype: %s" % (len(pkts), linktype))

    # Collect handshake components keyed by (src_mac, dst_mac) pair
    # For each station (STA MAC), we need:
    #   M1 (msg 1, AP->STA): AP nonce
    #   M2 (msg 2, STA->AP): STA nonce
    #   M3 (msg 3, AP->STA): AP MIC (keymic)
    #   M4 (msg 4, STA->AP): STA MIC
    # We want the handshake where both nonces are present.

    best = None  # (ap_nonce, sta_nonce, ap_mac, sta_mac, ap_mic, sta_mic, count)
    # track per-station
    per_sta = {}

    for pkt in pkts:
        fe = find_eapol(pkt, linktype)
        if not fe:
            continue
        eapol, dst, src = fe
        p = parse_eapol(eapol)
        if not p:
            continue
        mn = p["msg_num"]
        if mn not in (1, 2, 3, 4):
            continue
        sta = dst if mn in (1, 3) else src  # station side
        ap = src if mn in (1, 3) else dst
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

    # Prefer a record whose AP is the target BSSID and has both nonces.
    # M3/M4 (MICs) are optional: if missing, hashcat 22000 can still crack
    # with zero MICs (common in real captures).
    complete = []
    for sta, rec in per_sta.items():
        if rec["ap_nonce"] and rec["sta_nonce"]:
            ap_match = rec["ap"] is not None and rec["ap"] == target_b
            has_mics = (rec["ap_mic"] is not None and rec["sta_mic"] is not None)
            complete.append((2 if ap_match and has_mics else (1 if ap_match else 0), sta, rec))
    complete.sort(key=lambda x: x[0], reverse=True)

    if not complete:
        print("No complete handshake found. Stations seen: %d" % len(per_sta))
        for sta, rec in list(per_sta.items())[:10]:
            print("  sta=%s ap=%s msgs=%s ap_nonce=%s sta_nonce=%s" % (
                sta.hex(), (rec["ap"] or b"").hex(), sorted(rec["msgs"]),
                (rec["ap_nonce"] or b"").hex()[:16], (rec["sta_nonce"] or b"").hex()[:16]))
        die("no complete handshake")

    _, sta, rec = complete[0]
    ap = rec["ap"]
    ap_nonce = rec["ap_nonce"]
    sta_nonce = rec["sta_nonce"]
    ap_mic = rec["ap_mic"]
    sta_mic = rec["sta_mic"]

    # Get SSID: scan for 802.11 beacons/probes with SSID
    ssid = None
    for pkt in pkts:
        # 802.11 frame: first byte type. Management type 0 (beacon) / 2 (probe)
        if len(pkt) < 24:
            continue
        ftype = pkt[0] & 0x0F
        if ftype not in (0, 2):
            continue
        # parse 802.11 header: dur(2) fctl(2) dur... actually:
        # [0:2]=dur, [2:4]=fctl, [4:8]=seq/ack, [8:16]=addr1, [16:22]=addr2, [22:28]=addr3
        # For beacon: addr2 = AP
        # Frame body starts after header. Header length depends on addr count.
        # fctl bits: toDS(bit0), fromDS(bit1)
        to_ds = pkt[2] & 0x01
        from_ds = pkt[2] & 0x02
        naddr = 2 + to_ds + from_ds
        hlen = 2 + 2 + 4 + 6 * naddr
        if len(pkt) < hlen:
            continue
        # Find SSID: search for 0x00 0x08 0x03 0x00 (SSID elem id 0, len 3)
        idx = pkt.find(bytes([0x00, 0x08, 0x03, 0x00]))
        if idx != -1 and idx + 9 < len(pkt):
            ssid = pkt[idx+3:idx+9].decode("latin-1", "replace")
            # validate
            if all(32 <= ord(c) < 127 for c in ssid):
                break

    if not ssid:
        ssid = "32H9F_5G"
        print("WARN: SSID not found in capture, using default")

    # hashcat 22000 format:
    # <essid>:<bssid>:<essid-escaped>:<mac-sta>:<mac-ap>:<nonce-sta>:<nonce-ap>:<keymic-sta>:<keymic-ap>:<ekey-sta>:<ekey-ap>
    # essid-escaped: non-printable chars as \xHH
    ssid_esc = ""
    for ch in ssid.encode("latin-1"):
        if 32 <= ch < 127:
            ssid_esc += chr(ch)
        else:
            ssid_esc += "\\x%02x" % ch

    # If MICs are missing, use zero MICs (hashcat 22000 accepts this).
    ap_mic_h = (ap_mic or b"\x00"*32).hex() if ap_mic else "0"*32
    sta_mic_h = (sta_mic or b"\x00"*32).hex() if sta_mic else "0"*32

    h = "%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s" % (
        ssid,
        mac_hex(ap),
        ssid_esc,
        mac_hex(sta),
        mac_hex(ap),
        sta_nonce.hex(),
        ap_nonce.hex(),
        ap_mic_h,
        sta_mic_h,
        "0"*32,
        "0"*32,
    )

    print("\n=== HANDSHAKE FOUND ===")
    print("SSID:    %s" % ssid)
    print("AP:      %s" % mac_hex(ap))
    print("STA:     %s" % mac_hex(sta))
    print("AP nonce:    %s" % ap_nonce.hex())
    print("STA nonce:   %s" % sta_nonce.hex())
    print("AP keymic:   %s" % (ap_mic.hex() if ap_mic else "(missing)"))
    print("STA keymic:  %s" % (sta_mic.hex() if sta_mic else "(missing)"))
    print("\nhashcat 22000 hash:\n%s\n" % h)

    # write to hashes/
    import os
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hashes")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "32h9f.22000")
    with open(out, "w") as f:
        f.write(h + "\n")
    print("wrote %s" % out)

if __name__ == "__main__":
    main()
