"""Debug: check what the extractor sees."""
from collections import defaultdict
from scapy.all import rdpcap, Ether, EAPOL_KEY

pcap = r"C:\Users\crazydb911\Documents\deepseek\sudo_cap.pcap"
pkts = rdpcap(pcap)
print(f"Total packets: {len(pkts)}")

rsc_groups = defaultdict(list)
for i, pkt in enumerate(pkts):
    if not pkt.haslayer(EAPOL_KEY):
        continue
    ek = pkt[EAPOL_KEY]
    raw = bytes(ek)
    key_info = int.from_bytes(raw[1:3], 'big')
    msg_num = (key_info >> 8) & 0x03
    rsc = raw[13:17].hex()
    key_mic = raw[5:13].hex()
    key_data_len = int.from_bytes(raw[21:23], 'big')
    key_data = raw[23:23+key_data_len]
    nonce = key_data[:32].hex() if key_data_len >= 32 else ''
    dst_mac = '000000000000'
    src_mac = '000000000000'
    if pkt.haslayer(Ether):
        eth = pkt[Ether]
        dst_mac = str(eth.dst).replace(':', '').lower()
        src_mac = str(eth.src).replace(':', '').lower()
    
    print(f"\nFrame {i}:")
    print(f"  msg_num={msg_num}, rsc={rsc}")
    print(f"  key_mic={key_mic}")
    print(f"  key_data_len={key_data_len}")
    print(f"  nonce={nonce[:40]}...")
    print(f"  dst={dst_mac}, src={src_mac}")
    
    rsc_groups[rsc].append({
        'msg_num': msg_num, 'dst_mac': dst_mac, 'src_mac': src_mac,
        'nonce': nonce, 'mic': key_mic, 'raw': raw
    })

print(f"\n\nRSC groups: {len(rsc_groups)}")
for rsc, group in rsc_groups.items():
    m1 = [f for f in group if f['msg_num'] in (1, 0)]
    m3 = [f for f in group if f['msg_num'] == 3]
    print(f"  RSC={rsc}: M1={len(m1)}, M3={len(m3)}")
    for f in group:
        print(f"    msg_num={f['msg_num']}, nonce={f['nonce'][:30]}..., mic={f['mic']}")
