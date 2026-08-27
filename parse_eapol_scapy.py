#!/usr/bin/env python3
"""
Parse EAPOL frames from PCAPNG using scapy and extract 22000 hash
"""
import sys
from collections import defaultdict
from scapy.all import rdpcap, EAPOL, EAPOL_KEY, Dot11

def extract_22000_hash(pkts, ssid):
    """Extract 22000 hash from EAPOL packets"""
    # Group frames by RSC (pairing key)
    rsc_groups = defaultdict(list)
    
    for pkt in pkts:
        if pkt.haslayer(EAPOL_KEY):
            eapol_key = pkt[EAPOL_KEY]
            
            # Message Number (smk_message field)
            msg_num = eapol_key.smk_message
            
            # Key RSC (pairing key)
            key_rsc = eapol_key.key_rsc
            
            # Key MIC
            key_mic = eapol_key.key_mic
            
            # Key Nonce
            key_nonce = eapol_key.key_nonce
            
            # MAC addresses
            dot11 = pkt[Dot11]
            dst_mac = dot11.addr1
            src_mac = dot11.addr2
            
            # Convert to hex strings
            rsc_hex = key_rsc.hex() if hasattr(key_rsc, 'hex') else bytes(key_rsc).hex()
            mic_hex = key_mic.hex() if hasattr(key_mic, 'hex') else bytes(key_mic).hex()
            nonce_hex = key_nonce.hex() if hasattr(key_nonce, 'hex') else bytes(key_nonce).hex()
            
            rsc_groups[rsc_hex].append({
                'msg_num': msg_num,
                'dst_mac': dst_mac,
                'src_mac': src_mac,
                'key_rsc': key_rsc,
                'key_mic': key_mic,
                'key_nonce': key_nonce,
                'mic_hex': mic_hex,
                'nonce_hex': nonce_hex,
                'raw': eapol_key
            })
    
    # Find M1 + M3 pairs
    hashes = []
    ssid_bytes = ssid.encode('utf-8')
    essid_hex = ssid_bytes.hex()
    
    for rsc, group in rsc_groups.items():
        m1 = [f for f in group if f['msg_num'] == 1]
        m3 = [f for f in group if f['msg_num'] == 3]
        
        if m1 and m3:
            m1_frame = m1[0]
            m3_frame = m3[0]
            
            # AP MAC (M1 src_mac)
            ap_mac = m1_frame['src_mac'].replace(':', '')
            
            # STA MAC (M1 dst_mac)
            sta_mac = m1_frame['dst_mac'].replace(':', '')
            
            # ANonce (M1 nonce)
            anonce = m1_frame['nonce_hex']
            
            # SNonce (M3 nonce)
            snonce = m3_frame['nonce_hex']
            
            # KEYMIC (M3 key_mic)
            key_mic = m3_frame['mic_hex']
            
            # EAPOL frame (M3 raw)
            eapol_hex = bytes(m3_frame['raw']).hex()
            
            # Message pair
            msgpair = "03"
            
            # Build 22000 hash
            hash_str = f"WPA*02*{key_mic}*{ap_mac}*{sta_mac}*{essid_hex}*{anonce}*{eapol_hex}*{msgpair}"
            
            hashes.append(hash_str)
    
    return hashes, rsc_groups

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <pcapng_file> <ssid>")
        sys.exit(1)
    
    pcapng_file = sys.argv[1]
    ssid = sys.argv[2] if len(sys.argv) > 2 else "32H9F_5G"
    
    print(f"Reading {pcapng_file}...")
    pkts = rdpcap(pcapng_file)
    print(f"Total packets: {len(pkts)}")
    
    # Count EAPOL_KEY packets
    eapol_key_pkts = [pkt for pkt in pkts if pkt.haslayer(EAPOL_KEY)]
    print(f"EAPOL_KEY packets: {len(eapol_key_pkts)}")
    
    # Message number distribution
    msg_counts = defaultdict(int)
    for pkt in eapol_key_pkts:
        eapol_key = pkt[EAPOL_KEY]
        msg_num = eapol_key.smk_message
        msg_counts[msg_num] += 1
    
    print("Message number distribution:")
    for msg_num in sorted(msg_counts.keys()):
        print(f"  Msg {msg_num}: {msg_counts[msg_num]} packets")
    
    # Extract hashes
    hashes, rsc_groups = extract_22000_hash(pkts, ssid)
    print(f"\nRSC groups: {len(rsc_groups)}")
    print(f"Extracted {len(hashes)} 22000 hashes")
    
    # Check ANonce == SNonce
    identical_nonce_count = 0
    for rsc, group in rsc_groups.items():
        m1 = [f for f in group if f['msg_num'] == 1]
        m3 = [f for f in group if f['msg_num'] == 3]
        
        if m1 and m3:
            m1_nonce = m1[0]['nonce_hex']
            m3_nonce = m3[0]['nonce_hex']
            if m1_nonce == m3_nonce:
                identical_nonce_count += 1
                print(f"  RSC {rsc}: ANonce == SNonce (identical!)")
            else:
                print(f"  RSC {rsc}: ANonce != SNonce (different)")
    
    print(f"\nIdentical nonce count: {identical_nonce_count}/{len(rsc_groups)}")
    
    for i, h in enumerate(hashes):
        print(f"\nHash {i+1}:")
        print(h)
    
    # Write to file
    output_file = pcapng_file.replace('.pcapng', '.hc22000')
    with open(output_file, 'w') as f:
        for h in hashes:
            f.write(h + '\n')
    
    print(f"\nSaved to {output_file}")

if __name__ == '__main__':
    main()
