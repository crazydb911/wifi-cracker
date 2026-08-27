#!/usr/bin/env python3
"""
Extract 22000 hash from PCAPNG - final corrected version
Uses raw bytes for RSC (scapy key_rsc is wrong)
"""
import sys
from collections import defaultdict
from scapy.all import rdpcap, EAPOL_KEY, Ether

def parse_eapol_key(ek):
    """Parse EAPOL_KEY raw bytes"""
    raw = bytes(ek)
    # raw[0] = KeyDescType (0x02)
    # raw[1:3] = KeyInfo
    # raw[3:5] = KeyLength
    # raw[5:13] = KeyIV (8 bytes)
    # raw[13:17] = KeyRSC (4 bytes)
    # raw[17:21] = KeyMIC (4 bytes)
    # raw[21:23] = KeyDataLength
    # raw[23:] = KeyData
    
    key_info = int.from_bytes(raw[1:3], 'big')
    msg_num = (key_info >> 8) & 0x03
    rsc = raw[13:17]
    mic = raw[17:21]
    key_data_len = int.from_bytes(raw[21:23], 'big')
    key_data = raw[23:23+key_data_len] if key_data_len > 0 else b''
    nonce = key_data[:32] if len(key_data) >= 32 else b'\x00' * 32
    
    return {
        'msg_num': msg_num,
        'rsc': rsc.hex(),
        'mic': mic.hex(),
        'nonce': nonce.hex(),
        'raw': raw,
    }

def main():
    pcapng_file = sys.argv[1]
    ssid = sys.argv[2] if len(sys.argv) > 2 else "32H9F_5G"
    
    print(f"Reading {pcapng_file}...")
    pkts = rdpcap(pcapng_file)
    print(f"Total packets: {len(pkts)}")
    
    # Group by RSC (using raw bytes)
    rsc_groups = defaultdict(list)
    msg_counts = defaultdict(int)
    
    for pkt in pkts:
        if not pkt.haslayer(EAPOL_KEY):
            continue
        
        ek = pkt[EAPOL_KEY]
        parsed = parse_eapol_key(ek)
        msg_counts[parsed['msg_num']] += 1
        
        # Extract MACs from Ether layer
        dst_mac = '000000000000'
        src_mac = '000000000000'
        if pkt.haslayer(Ether):
            eth = pkt[Ether]
            dst_mac = str(eth.dst).replace(':', '')
            src_mac = str(eth.src).replace(':', '')
        
        rsc_groups[parsed['rsc']].append({
            'msg_num': parsed['msg_num'],
            'dst_mac': dst_mac,
            'src_mac': src_mac,
            'nonce': parsed['nonce'],
            'mic': parsed['mic'],
            'raw': parsed['raw'],
        })
    
    print(f"\nMessage number distribution:")
    for msg_num in sorted(msg_counts.keys()):
        print(f"  Msg {msg_num}: {msg_counts[msg_num]} packets")
    
    print(f"\nRSC groups: {len(rsc_groups)}")
    
    # Show all RSC groups with M1+M3
    pairs = 0
    for rsc, group in sorted(rsc_groups.items()):
        m1 = [f for f in group if f['msg_num'] == 1]
        m3 = [f for f in group if f['msg_num'] == 3]
        if m1 and m3:
            pairs += 1
            nonce_match = "SAME" if m1[0]['nonce'] == m3[0]['nonce'] else "DIFF"
            print(f"  RSC {rsc}: M1={len(m1)} M3={len(m3)} nonce={nonce_match} ap={m1[0]['src_mac']} sta={m1[0]['dst_mac']}")
    
    print(f"\nM1+M3 pairs: {pairs}")
    
    # Build hashes for all pairs
    ssid_hex = ssid.encode('utf-8').hex()
    hashes = []
    
    for rsc, group in sorted(rsc_groups.items()):
        m1 = [f for f in group if f['msg_num'] == 1]
        m3 = [f for f in group if f['msg_num'] == 3]
        
        if not (m1 and m3):
            continue
        
        m1f = m1[0]
        m3f = m3[0]
        
        # AP MAC: source of M1 (AP sends M1)
        ap_mac = m1f['src_mac']
        # STA MAC: destination of M1 (AP sends to STA)
        sta_mac = m1f['dst_mac']
        anonce = m1f['nonce']
        key_mic = m3f['mic']
        
        # Full EAPOL frame hex: reconstruct from raw
        # raw starts at KeyDescType. Prepend version(1) + type(1) + length(2 BE)
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
