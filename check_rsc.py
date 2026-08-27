#!/usr/bin/env python3
from scapy.all import rdpcap, EAPOL_KEY
pkts = rdpcap('C:/Users/crazydb911/Documents/deepseek/32h9f_eapol.pcapng')

print("Checking key_rsc values:")
for i, pkt in enumerate(pkts[:10]):
    if pkt.haslayer(EAPOL_KEY):
        ek = pkt[EAPOL_KEY]
        print(f"Packet {i}: key_rsc={ek.key_rsc.hex()} nonce={ek.key_nonce[:8].hex()}...")
        # Also check raw bytes
        raw = bytes(ek)
        print(f"  Raw bytes 0-30: {raw[:30].hex()}")
        # Key RSC should be at raw offset 17-21 (4 bytes)
        # raw[0]=KeyDescType, raw[1:3]=KeyInfo, raw[3:5]=KeyLen, raw[5:13]=KeyIV, raw[13:17]=KeyRSC
        print(f"  Raw[13:17] (should be RSC): {raw[13:17].hex()}")
