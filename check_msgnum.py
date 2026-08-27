#!/usr/bin/env python3
from scapy.all import rdpcap, EAPOL_KEY
pkts = rdpcap('C:/Users/crazydb911/Documents/deepseek/32h9f_eapol.pcapng')

print("Checking message number extraction:")
for i, pkt in enumerate(pkts[:5]):
    if pkt.haslayer(EAPOL_KEY):
        eapol_key = pkt[EAPOL_KEY]
        print(f"\nPacket {i}:")
        print(f"  smk_message: {eapol_key.smk_message}")
        print(f"  key_nonce: {eapol_key.key_nonce}")
        print(f"  key_mic: {eapol_key.key_mic}")
        
        # Try to extract raw bytes
        raw = bytes(eapol_key)
        print(f"  Raw first 30 bytes: {raw[:30].hex()}")
        
        # Message number is at offset 5-6 in EAPOL_KEY (Key Information)
        # Bit 8-9 of Key Information
        key_info = int.from_bytes(raw[0:2], 'big')
        msg_num = (key_info >> 8) & 0x03
        print(f"  Key Info: {key_info:#06x}")
        print(f"  Msg Num (bits 8-9): {msg_num}")
