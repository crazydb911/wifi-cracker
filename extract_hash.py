#!/usr/bin/env python3
"""
Extract 22000 hash from PCAPNG using scapy
Corrected: EAPOL_KEY raw starts at KeyDescType (skips 3-byte EAPOL header)
  raw[0] = KeyDescType (0x02)
  raw[1:3] = KeyInfo (big-endian)
  raw[3:5] = KeyLength
  raw[5:13] = KeyIV
  raw[13:17] = KeyRSC
  raw[17:21] = KeyMIC
  raw[21:23] = KeyDataLength
  raw[23:] = KeyData (first 32 bytes = Nonce)
"""
import sys
from collections import defaultdict
from scapy.all import rdpcap, EAPOL_KEY

def get_msg_num(eapol_key):
    raw = bytes(eapol_key)
    key_info = int.from_bytes(raw[1:3], 'big')
    return (key_info >> 8) & 0x03

def main():
    pcapng_file = sys.argv[1]
    ssid = sys.argv[2] if len(sys.argv) > 2 else "32H9F_5G"
    
    print(f"Reading {pcapng_file}...")
    pkts = rdpcap(pcapng_file)
    print(f"Total packets: {len(pkts)}")
    
    eapol_key_pkts = [pkt for pkt in pkts if pkt.haslayer(EAPOL_KEY)]
    print(f"EAPOL_KEY packets: {len(eapol_key_pkts)}")
    
    # Message number distribution
    msg_counts = defaultdict(int)
    for pkt in eapol_key_pkts:
        msg_num = get_msg_num(pkt[EAPOL_KEY])
        msg_counts[msg_num] += 1
    
    print("Message number distribution:")
    for msg_num in sorted(msg_counts.keys()):
        print(f"  Msg {msg_num}: {msg_counts[msg_num]} packets")
    
    # Group by RSC
    rsc_groups = defaultdict(list)
    for pkt in eapol_key_pkts:
        ek = pkt[EAPOL_KEY]
        msg_num = get_msg_num(ek)
        rsc_hex = ek.key_rsc.hex()
        
        # Get MAC addresses from the packet
        dst_mac = ''
        src_mac = ''
        for layer in pkt:
            if 'addr1' in dir(layer) or hasattr(layer, 'addr1'):
                dst_mac = str(layer.addr1).replace(':', '')
                src_mac = str(layer.addr2).replace(':', '')
                break
        
        rsc_groups[rsc_hex].append({
            'msg_num': msg_num,
            'dst_mac': dst_mac,
            'src_mac': src_mac,
            'nonce': ek.key_nonce,
            'mic': ek.key_mic,
            'raw': ek,
        })
    
    print(f"\nRSC groups: {len(rsc_groups)}")
    
    # Check ANonce == SNonce
    identical = 0
    for rsc, group in rsc_groups.items():
        m1 = [f for f in group if f['msg_num'] == 1]
        m3 = [f for f in group if f['msg_num'] == 3]
        if m1 and m3:
            if m1[0]['nonce'].hex() == m3[0]['nonce'].hex():
                identical += 1
                print(f"  RSC {rsc}: ANonce == SNonce")
            else:
                print(f"  RSC {rsc}: ANonce != SNonce")
    print(f"Identical nonce: {identical}/{len(rsc_groups)}")
    
    # Build hashes
    ssid_hex = ssid.encode('utf-8').hex()
    hashes = []
    
    for rsc, group in rsc_groups.items():
        m1 = [f for f in group if f['msg_num'] == 1]
        m3 = [f for f in group if f['msg_num'] == 3]
        
        if not (m1 and m3):
            continue
        
        m1f = m1[0]
        m3f = m3[0]
        
        ap_mac = m1f['src_mac']
        sta_mac = m1f['dst_mac']
        anonce = m1f['nonce'].hex()
        snonce = m3f['nonce'].hex()
        key_mic = m3f['mic'].hex()
        
        # Full EAPOL frame hex: reconstruct from raw EAPOL_KEY
        # raw already starts at KeyDescType. Prepend version(1) + type(1) + length(2)
        ek_raw = bytes(m3f['raw'])
        # EAPOL length field = total EAPOL length (KeyDescType + rest)
        eapol_len = len(ek_raw)
        # Full frame = version + type + length(2 BE) + key descriptor
        full_frame = bytes([1, 0x03]) + eapol_len.to_bytes(2, 'big') + ek_raw
        
        # Token 8: full EAPOL frame hex
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
