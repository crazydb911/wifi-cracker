import struct

with open("/tmp/mac_all.cap", "rb") as f:
    data = f.read()

print("File size: %d bytes" % len(data))
print("First 48 bytes: %s" % data[:48].hex())

# Try both big and little endian
magic_be = struct.unpack(">I", data[:4])[0]
magic_le = struct.unpack("<I", data[:4])[0]
print("Big-endian magic: %x" % magic_be)
print("Little-endian magic: %x" % magic_le)

# Determine byte order
if magic_be == 0xa1b2c3d4:
    order = ">"
    print("Big-endian pcap")
elif magic_le == 0xa1b2c3d4:
    order = "<"
    print("Little-endian pcap")
elif data[:4] == b"\x0a\x0d\x0d\x0a":
    print("Pcapng file")
else:
    print("Unknown format")
    exit(1)

# Parse header
if order == ">":
    ver_maj, ver_min = struct.unpack(">HH", data[4:8])
    thiszone, sigfigs = struct.unpack(">ii", data[8:16])
    snaplen, network = struct.unpack(">II", data[16:24])
else:
    ver_maj, ver_min = struct.unpack("<HH", data[4:8])
    thiszone, sigfigs = struct.unpack("<ii", data[8:16])
    snaplen, network = struct.unpack("<II", data[16:24])

print("Version: %d.%d" % (ver_maj, ver_min))
print("Network: %d" % network)
print("Snaplen: %d" % snaplen)

# Parse packets
offset = 24
count = 0
eapol_count = 0
frame_counts = [0, 0, 0, 0]
eapol_frames = []

while offset + 16 <= len(data):
    ts_sec, ts_usec, incl_len, orig_len = struct.unpack(order + "IIII", data[offset:offset+16])
    offset += 16
    
    if incl_len == 0 or offset + incl_len > len(data):
        if count < 3:
            print("  Bad packet at offset %d: incl_len=%d, remaining=%d" % (offset, incl_len, len(data)-offset))
        break
    
    pkt_data = data[offset:offset+incl_len]
    offset += incl_len
    count += 1
    
    if count <= 3:
        print("Packet %d: %d bytes" % (count, incl_len))
    
    # Search for EAPOL marker
    eapol_marker = bytes([0xAA, 0xAA, 0x03, 0x00, 0x00, 0x00, 0x00, 0x88, 0x8E])
    idx = pkt_data.find(eapol_marker)
    
    if idx == -1:
        # Try without LLC/SNAP
        idx = pkt_data.find(b"\x88\x8e")
    
    if idx != -1:
        eapol_count += 1
        eapol_start = idx + 9 if idx >= 0 else 0
        if eapol_start + 4 < len(pkt_data):
            key_info = struct.unpack(">H", pkt_data[eapol_start+2:eapol_start+4])[0]
            msg_num = (key_info >> 12) & 0x3
            eapol_type = pkt_data[eapol_start]
            
            if eapol_type == 0 and msg_num in [1,2,3,4]:
                frame_counts[msg_num-1] += 1
                eapol_frames.append(pkt_data[eapol_start:eapol_start+min(64, len(pkt_data)-eapol_start)])
        
        if eapol_count <= 5:
            print("  EAPOL #%d at offset %d" % (eapol_count, idx))

print("")
print("Total packets: %d" % count)
print("EAPOL frames: %d" % eapol_count)
print("Frame 1 (ANonce): %d" % frame_counts[0])
print("Frame 2 (SNonce): %d" % frame_counts[1])
print("Frame 3 (MIC): %d" % frame_counts[2])
print("Frame 4 (MIC): %d" % frame_counts[3])

# Write EAPOL frames to a new pcap
if eapol_frames:
    with open("/tmp/32h9f_eapol.cap", "wb") as out:
        # Global header (little-endian)
        out.write(struct.pack("<IHHiIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))
        for frame in eapol_frames:
            out.write(struct.pack("<IIII", 0, 0, len(frame), len(frame)))
            out.write(frame)
    print("Wrote %d EAPOL frames to /tmp/32h9f_eapol.cap" % len(eapol_frames))
