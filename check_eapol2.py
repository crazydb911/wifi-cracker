"""Check EAPOL with scapy (no tshark needed)."""
from scapy.all import rdpcap, EAPOL_KEY, EAPOL, Ether

pcap = r"C:\Users\crazydb911\Documents\deepseek\sudo_cap.pcap"
pkts = rdpcap(pcap)
print(f"Total packets: {len(pkts)}")

eapol_count = 0
for i, pkt in enumerate(pkts):
    if pkt.haslayer(EAPOL_KEY):
        eapol_count += 1
        raw = bytes(pkt[EAPOL_KEY])
        # Parse EAPOL-Key manually
        # raw[0] = type (2)
        # raw[1:3] = KeyInfo (msg_num = bits 30-31)
        key_info = int.from_bytes(raw[1:3], 'big')
        msg_num = (key_info >> 8) & 0x03
        key_rsc = raw[13:17].hex()
        key_data_len = int.from_bytes(raw[21:23], 'big')
        key_data = raw[23:23+key_data_len]
        
        print(f"\n=== EAPOL frame {i} (msg_num={msg_num}) ===")
        print(f"  KeyInfo: 0x{key_info:04x}")
        print(f"  KeyRSC: {key_rsc}")
        print(f"  KeyDataLen: {key_data_len}")
        
        # Check for nonce (should be 32 bytes in key_data)
        if key_data_len >= 32:
            nonce = key_data[:32].hex()
            print(f"  Nonce (first 32B): {nonce}")
            # Check if truncated (last 10 bytes are zeros)
            if key_data[22:32] == b'\x00' * 10:
                print(f"  WARNING: Nonce appears TRUNCATED (last 10B = zeros)")
            else:
                print(f"  Nonce looks complete")
        else:
            print(f"  No nonce (key_data too short: {key_data_len})")
        
        # Get src/dst from Ethernet
        if pkt.haslayer(Ether):
            print(f"  Src: {pkt[Ether].src}")
            print(f"  Dst: {pkt[Ether].dst}")

print(f"\nTotal EAPOL: {eapol_count}")
