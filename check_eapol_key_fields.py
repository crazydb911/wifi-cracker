#!/usr/bin/env python3
from scapy.all import rdpcap, EAPOL_KEY
pkts = rdpcap('C:/Users/crazydb911/Documents/deepseek/32h9f_eapol.pcapng')

pkt = pkts[0]
if pkt.haslayer(EAPOL_KEY):
    ek = pkt[EAPOL_KEY]
    print("EAPOL_KEY fields:")
    for field in ek.fields:
        val = ek.getfieldval(field)
        if isinstance(val, bytes):
            print(f"  {field}: {val.hex()} ({len(val)} bytes)")
        else:
            print(f"  {field}: {val}")
    print()
    print("Raw bytes:")
    raw = bytes(ek)
    print(f"  Length: {len(raw)}")
    print(f"  Hex: {raw.hex()}")
    print()
    # Check if there's a 16-byte MIC somewhere
    # raw[17:33] would be 16 bytes
    print(f"  raw[17:33] (16 bytes): {raw[17:33].hex()}")
