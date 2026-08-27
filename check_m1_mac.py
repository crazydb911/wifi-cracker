#!/usr/bin/env python3
from scapy.all import rdpcap, EAPOL_KEY, Ether
pkts = rdpcap('C:/Users/crazydb911/Documents/deepseek/32h9f_eapol.pcapng')

print("Checking M1 packets MAC addresses:")
count = 0
for i, pkt in enumerate(pkts):
    if pkt.haslayer(EAPOL_KEY):
        ek = pkt[EAPOL_KEY]
        raw = bytes(ek)
        key_info = int.from_bytes(raw[1:3], 'big')
        msg_num = (key_info >> 8) & 0x03
        
        if msg_num == 1:  # M1
            count += 1
            if pkt.haslayer(Ether):
                eth = pkt[Ether]
                print(f"Packet {i}: M1 dst={eth.dst} src={eth.src}")
            if count >= 5:
                break
