#!/usr/bin/env python3
from scapy.all import rdpcap, EAPOL
pkts = rdpcap('C:/Users/crazydb911/Documents/deepseek/32h9f_eapol.pcapng')
pkt = pkts[0]
if pkt.haslayer(EAPOL):
    eapol = pkt[EAPOL]
    print('EAPOL fields:')
    print(eapol.show2())
