#!/usr/bin/env python3
"""
Extract 22000 hash from PCAPNG - use scapy key_mic (16 bytes)
"""
import sys
from collections import defaultdict
from scapy.all import rdpcap, EAPOL_KEY, Ether

def main():
    pcapng_file = sys.argv[1]
    ssid = sys.argv[2] if len(sys.argv) > 2 else "32H9F_5G"
    ap_mac = sys.argv[3] if len(sys.argv) > 3 else "6c4f894ca0e4"
    
    print(f"Reading {pcapng_file}...")
    pkts = rdpcap(pcapng_file)
    print(f"Total packets: {len(pkts)}")
    
    rsc_groups = defaultdict(list)
    msg_counts = defaultdict(int)
    
    for pkt in pkts:
        if not pkt.haslayer(EAPOL_KEY):
            continue
        ek = pkt[EAPOL_KEY]
        
        # Get message number from raw bytes
        raw = bytes(ek)
        key_info = int.from_bytes(raw[1:3], 'big')
        msg_num = (key_info >> 8) & 0x03
        msg_counts[msg_num] += 1
        
        # Use scapy fields
        rsc = ek.key_rsc.hex()  # 8 bytes
        mic = ek.key_mic.hex()  # 16 bytes
        nonce = ek.key_nonce.hex()  # 32 bytes
        
        # Extract MACs
        dst_mac = '000000000000'
        src_mac = '000000000000'
        if pkt.haslayer(Ether):
            eth = pkt[Ether]
            dst_mac = str(eth.dst).replace(':', '')
            src_mac = str(eth.src).replace(':', '')
        
        rsc_groups[rsc].append({
            'msg_num': msg_num,
            'dst_mac': dst_mac,
            'src_mac': src_mac,
            'nonce': nonce,
            'mic': mic,
            'raw': raw,
        })
    
    print(f"\nMessage distribution:")
    for msg_num in sorted(msg_counts.keys()):
        print(f"  Msg {msg_num}: {msg_counts[msg_num]}")
    
    print(f"\nRSC groups: {len(rsc_groups)}")
    
    pairs = 0
    for rsc, group in sorted(rsc_groups.items()):
        m1 = [f for f in group if f['msg_num'] == 1]
        m3 = [f for f in group if f['msg_num'] == 3]
        if m1 and m3:
            pairs += 1
            nonce_match = "SAME" if m1[0]['nonce'] == m3[0]['nonce'] else "DIFF"
            mic_match = "SAME" if m1[0]['mic'] == m3[0]['mic'] else "DIFF"
            print(f"  RSC {rsc}: M1={len(m1)} M3={len(m3)} nonce={nonce_match} mic={mic_match}")
    
    print(f"\nM1+M3 pairs: {pairs}")
    
    ssid_hex = ssid.encode('utf-8').hex()
    hashes = []
    
    for rsc, group in sorted(rsc_groups.items()):
        m1 = [f for f in group if f['msg_num'] == 1]
        m3 = [f for f in group if f['msg_num'] == 3]
        if not (m1 and m3):
            continue
        
        m1f = m1[0]
        m3f = m3[0]
        
        # AP MAC: known
        # STA MAC: source of M1
        sta_mac = m1f['src_mac']
        anonce = m1f['nonce']
        key_mic = m3f['mic']  # 16 bytes from M3
        
        # Full EAPOL frame hex
        ek_raw = m3f['raw']
        eapol_len = len(ek_raw)
        full_frame = bytes([1, 0x03]) + eapol_len.to_bytes(2, 'big') + ek_raw
        eapol_hex = full_frame.hex()
        
        hash_str = f"WPA*02*{key_mic}*{ap_mac}*{sta_mac}*{ssid_hex}*{anonce}*{eapol_hex}*03"
        hashes.append(hash_str)
    
    print(f"\nExtracted {len(hashes)} 22000 hashes")
    for i, h in enumerate(hashes):
        print(f"\nHash {i+1}:")
        print(h)
    
    output_file = pcapng_file.replace('.pcapng', '.hc22000')
    with open(output_file, 'w') as f:
        for h in hashes:
            f.write(h + '\n')
    print(f"\nSaved to {output_file}")

if __name__ == '__main__':
    main()
