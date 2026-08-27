#!/usr/bin/env python3
from scapy.all import rdpcap, EAPOL_KEY
pkts = rdpcap('C:/Users/crazydb911/Documents/deepseek/32h9f_eapol.pcapng')

pkt = pkts[0]
if pkt.haslayer(EAPOL_KEY):
    ek = pkt[EAPOL_KEY]
    raw = bytes(ek)
    print(f"Total raw length: {len(raw)} bytes")
    print(f"Raw hex: {raw.hex()}")
    print()
    print("Parsing structure:")
    print(f"  [0] KeyDescType: {raw[0]:02x}")
    print(f"  [1:3] KeyInfo: {raw[1:3].hex()}")
    print(f"  [3:5] KeyLength: {int.from_bytes(raw[3:5], 'big')}")
    print(f"  [5:13] KeyIV (8 bytes): {raw[5:13].hex()}")
    print(f"  [13:17] KeyRSC (4 bytes): {raw[13:17].hex()}")
    print(f"  [17:21] KeyMIC (4 bytes): {raw[17:21].hex()}")
    print(f"  [21:23] KeyDataLength: {int.from_bytes(raw[21:23], 'big')}")
    print(f"  [23:] KeyData: {raw[23:23+int.from_bytes(raw[21:23], 'big')].hex()}")
    print()
    print("Expected from hashcat auth_packet_t:")
    print("  wpa_key_nonce[32]: 32 bytes")
    print("  wpa_key_iv[16]: 16 bytes")
    print("  wpa_key_rsc[8]: 8 bytes")
    print("  wpa_key_id[8]: 8 bytes")
    print("  wpa_key_mic[16]: 16 bytes")
