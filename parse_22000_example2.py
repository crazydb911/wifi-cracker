# Parse the example 22000 hash format
example = "WPA*01*4d4fe7aac3a2cecab195321ceb99a7d0*fc690c158264*f4747f87f9f4*686173686361742d6573736964***"
parts = example.split("*")

print("Part 1:", parts[0], "(length:", len(parts[0]), ")")
print("Part 2:", parts[1], "(length:", len(parts[1]), ")")
print("Part 3:", parts[2], "(length:", len(parts[2]), ")")
print("Part 4:", parts[3], "(length:", len(parts[3]), ")")
print("Part 5:", parts[4], "(length:", len(parts[4]), ")")
print("Part 6:", parts[5], "(length:", len(parts[5]), ")")
print("Part 7:", parts[6], "(length:", len(parts[6]), ")")
print("Part 8:", parts[7], "(length:", len(parts[7]), ")")
print("Part 9:", parts[8], "(length:", len(parts[8]), ")")

# Check the hex values
print("\nPart 6 hex decoded:", bytes.fromhex(parts[5]).decode('utf-8'))

# Now let's try to understand the format
# WPA*01*PMKID*AP_MAC*STA_MAC*ESSID***
# WPA = prefix
# 01 = type (1=PMKID, 2=EAPOL)
# 4d4fe7aac3a2cecab195321ceb99a7d0 = PMKID (32 hex chars = 16 bytes)
# fc690c158264 = AP MAC (12 hex chars = 6 bytes)
# f4747f87f9f4 = STA MAC (12 hex chars = 6 bytes)
# 686173686361742d6573736964 = ESSID (26 hex chars = 13 bytes)

print("\nAP MAC:", parts[3])
print("STA MAC:", parts[4])
print("ESSID:", bytes.fromhex(parts[5]).decode('utf-8'))
