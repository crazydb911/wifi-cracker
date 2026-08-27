#!/usr/bin/env python3
"""
Parse EAPOL frames from PCAPNG and extract 22000 hash
Based on hashcat mode 22000 format
"""
import sys
import struct
from collections import defaultdict

def parse_pcapng(filename):
    """Parse PCAPNG file and extract EAPOL frames"""
    with open(filename, 'rb') as f:
        data = f.read()
    
    # PCAPNG magic
    if data[:4] != b'\x0a\x0d\x0d\x0a':
        print("Not a PCAPNG file")
        return []
    
    # Find all EAPOL frames (EtherType 0x888e)
    eapol_frames = []
    i = 4  # Skip global header block
    
    while i < len(data):
        # Block type (4 bytes)
        if i + 8 > len(data):
            break
        block_type = struct.unpack('<I', data[i:i+4])[0]
        total_length = struct.unpack('<I', data[i+4:i+8])[0]
        
        if block_type == 0x00000006:  # Interface Description Block (IDB)
            pass  # Skip IDB
        
        elif block_type == 0x00000003:  # Simple Packet Block (SPB)
            if i + 8 + 4 > len(data):
                break
            interface_id = struct.unpack('<I', data[i+8:i+12])[0]
            cap_len = struct.unpack('<I', data[i+12:i+16])[0]
            
            if cap_len > 0:
                pkt_data = data[i+16:i+16+cap_len]
                
                # Check for EAPOL (EtherType 0x888e at offset 12 in Ethernet)
                if len(pkt_data) >= 14:
                    eth_type = struct.unpack('>H', pkt_data[12:14])[0]
                    if eth_type == 0x888e:
                        # Extract MAC addresses from Ethernet header
                        dst_mac = pkt_data[0:6]
                        src_mac = pkt_data[6:12]
                        
                        # EAPOL payload starts at offset 14
                        eapol = pkt_data[14:]
                        if len(eapol) >= 26:
                            # EAPOL header
                            version = eapol[0]
                            packet_type = eapol[1]
                            length = struct.unpack('>H', eapol[2:4])[0]
                            
                            # Key Descriptor
                            key_desc_type = eapol[4]
                            key_info = struct.unpack('>H', eapol[5:7])[0]
                            key_len = struct.unpack('>H', eapol[7:9])[0]
                            key_iv = eapol[9:17]
                            key_rsc = eapol[17:21]
                            key_mic = eapol[21:25]
                            key_data_len = struct.unpack('>H', eapol[25:27])[0]
                            
                            # Message number (bits 8-9 of key_info)
                            msg_num = (key_info >> 8) & 0x03
                            
                            # Key Data starts at offset 29
                            key_data = eapol[29:29+key_data_len] if key_data_len > 0 else b''
                            
                            # Nonce (first 32 bytes of key_data)
                            nonce = key_data[:32] if len(key_data) >= 32 else b'\x00' * 32
                            
                            eapol_frames.append({
                                'dst_mac': dst_mac,
                                'src_mac': src_mac,
                                'version': version,
                                'packet_type': packet_type,
                                'length': length,
                                'key_desc_type': key_desc_type,
                                'key_info': key_info,
                                'key_len': key_len,
                                'key_iv': key_iv,
                                'key_rsc': key_rsc,
                                'key_mic': key_mic,
                                'key_data_len': key_data_len,
                                'msg_num': msg_num,
                                'nonce': nonce,
                                'key_data': key_data,
                                'raw': eapol
                            })
        
        i += total_length
    
    return eapol_frames

def mac_to_hex(mac):
    """Convert MAC bytes to hex string (no colons)"""
    return mac.hex()

def extract_22000_hash(frames, ssid_bytes):
    """Extract 22000 hash from EAPOL frames"""
    # Group frames by RSC (pairing key)
    rsc_groups = defaultdict(list)
    for frame in frames:
        rsc = frame['key_rsc'].hex()
        rsc_groups[rsc].append(frame)
    
    # Find M1 + M3 pairs
    hashes = []
    for rsc, group in rsc_groups.items():
        m1 = [f for f in group if f['msg_num'] == 1]
        m3 = [f for f in group if f['msg_num'] == 3]
        
        if m1 and m3:
            # Use M1 for ANonce, M3 for SNonce + MIC
            m1_frame = m1[0]
            m3_frame = m3[0]
            
            # AP MAC (from M1 src_mac or M3 dst_mac)
            ap_mac = mac_to_hex(m1_frame['src_mac'])
            
            # STA MAC (from M1 dst_mac or M3 src_mac)
            sta_mac = mac_to_hex(m1_frame['dst_mac'])
            
            # ANonce (M1 nonce)
            anonce = m1_frame['nonce'].hex()
            
            # SNonce (M3 nonce)
            snonce = m3_frame['nonce'].hex()
            
            # KEYMIC (M3 key_mic)
            key_mic = m3_frame['key_mic'].hex()
            
            # ESSID (hex)
            essid_hex = ssid_bytes.hex()
            
            # EAPOL frame (M3 raw)
            eapol_hex = m3_frame['raw'].hex()
            
            # Message pair
            msgpair = "03"
            
            # Build 22000 hash
            # Format: WPA*02*<32hex PMKID/KEYMIC>*<12hex apmac>*<12hex stamac>*<essid hex>*<64hex ANonce>*<full EAPOL frame hex>*<2hex msgpair>
            hash_str = f"WPA*02*{key_mic}*{ap_mac}*{sta_mac}*{essid_hex}*{anonce}*{eapol_hex}*{msgpair}"
            
            hashes.append(hash_str)
    
    return hashes

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <pcapng_file> <ssid>")
        sys.exit(1)
    
    pcapng_file = sys.argv[1]
    ssid = sys.argv[2] if len(sys.argv) > 2 else "32H9F_5G"
    ssid_bytes = ssid.encode('utf-8')
    
    print(f"Parsing {pcapng_file}...")
    frames = parse_pcapng(pcapng_file)
    print(f"Found {len(frames)} EAPOL frames")
    
    # Group by message number
    msg_counts = defaultdict(int)
    for frame in frames:
        msg_counts[frame['msg_num']] += 1
    
    print("Message number distribution:")
    for msg_num in sorted(msg_counts.keys()):
        print(f"  Msg {msg_num}: {msg_counts[msg_num]} frames")
    
    # Check ANonce == SNonce
    rsc_groups = defaultdict(lambda: {'m1': [], 'm3': []})
    for frame in frames:
        rsc = frame['key_rsc'].hex()
        if frame['msg_num'] == 1:
            rsc_groups[rsc]['m1'].append(frame)
        elif frame['msg_num'] == 3:
            rsc_groups[rsc]['m3'].append(frame)
    
    print(f"\nRSC groups: {len(rsc_groups)}")
    identical_nonce_count = 0
    for rsc, group in rsc_groups.items():
        if group['m1'] and group['m3']:
            m1_nonce = group['m1'][0]['nonce'].hex()
            m3_nonce = group['m3'][0]['nonce'].hex()
            if m1_nonce == m3_nonce:
                identical_nonce_count += 1
                print(f"  RSC {rsc}: ANonce == SNonce (identical!)")
            else:
                print(f"  RSC {rsc}: ANonce != SNonce (different)")
    
    print(f"\nIdentical nonce count: {identical_nonce_count}/{len(rsc_groups)}")
    
    # Extract hashes
    hashes = extract_22000_hash(frames, ssid_bytes)
    print(f"\nExtracted {len(hashes)} 22000 hashes")
    
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
