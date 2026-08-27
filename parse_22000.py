#!/usr/bin/env python3
"""Parse the 22000 hash format correctly.
   
   The 22000 format is: ESSID:AP_MAC:STA_MAC:ANonce:SNonce:KeyMicAP:KeyMicSTA:EKeyAP:EKeySTA
   But the MAC addresses have colons, which conflict with the field separator.
   
   We need to parse it by finding the known field lengths.
"""
import re

# Read the 22000 hash
with open(r"C:\Users\crazydb911\Documents\deepseek\hashes\32h9f.22000", "r") as f:
    line = f.read().strip()

print("Hash line:", line)
print()

# The format is:
# ESSID:AP_MAC:STA_MAC:ANonce:SNonce:KeyMicAP:KeyMicSTA:EKeyAP:EKeySTA
#
# ESSID = 32H9F_5G (8 chars, no colons)
# AP_MAC = 6c:4f:89:4c:a0:e4 (17 chars, 5 colons)
# STA_MAC = 78:e2:67:25:87:00 (17 chars, 5 colons)
# ANonce = 0a0000000000000000000285b67a44f07ab6a6969e039ede82d16414adbf3c43 (64 chars)
# SNonce = f1f1592c440620a150a7ff00000000000000000000000000000000000000000 (64 chars)
# KeyMicAP = 00000000000000000000000000000000 (32 chars)
# KeyMicSTA = 00000000000000000000000000000000 (32 chars)
# EKeyAP = 00000000000000000000000000000000 (32 chars)
# EKeySTA = 00000000000000000000000000000000 (32 chars)

# Let's parse it by finding the known field lengths.
# The hash line should have exactly 9 fields separated by colons.
# But the MAC addresses have colons, so the split gives more parts.

# Strategy: find the positions of the known field lengths.
# ESSID is the first field (no colons)
# AP_MAC is the second field (5 colons)
# STA_MAC is the third field (5 colons)
# ANonce is the fourth field (no colons)
# SNonce is the fifth field (no colons)
# KeyMicAP is the sixth field (no colons)
# KeyMicSTA is the seventh field (no colons)
# EKeyAP is the eighth field (no colons)
# EKeySTA is the ninth field (no colons)

# Let's parse it by finding the known field lengths.
# The hash line is:
# 32H9F_5G:6c:4f:89:4c:a0:e4:78:e2:67:25:87:00:0a0000000000000000000285b67a44f07ab6a6969e039ede82d16414adbf3c43:f1f1592c440620a150a7ff000000000000000000000000000000000000000000:00000000000000000000000000000000:00000000000000000000000000000000:00000000000000000000000000000000:00000000000000000000000000000000

# Let's find the positions of the fields.
# ESSID starts at position 0
essid_start = 0
essid_end = line.index(":")
essid = line[essid_start:essid_end]
print("ESSID: %s" % essid)

# AP_MAC starts at position essid_end + 1
ap_start = essid_end + 1
# AP_MAC has 5 colons, so it ends at position ap_start + 17
ap_end = ap_start + 17
ap = line[ap_start:ap_end]
print("AP_MAC: %s" % ap)

# STA_MAC starts at position ap_end + 1
sta_start = ap_end + 1
# STA_MAC has 5 colons, so it ends at position sta_start + 17
sta_end = sta_start + 17
sta = line[sta_start:sta_end]
print("STA_MAC: %s" % sta)

# ANonce starts at position sta_end + 1
anonce_start = sta_end + 1
# ANonce is 64 chars
anonce_end = anonce_start + 64
anonce = line[anonce_start:anonce_end]
print("ANonce: %s" % anonce)

# SNonce starts at position anonce_end + 1
snonce_start = anonce_end + 1
# SNonce is 64 chars
snonce_end = snonce_start + 64
snonce = line[snonce_start:snonce_end]
print("SNonce: %s" % snonce)

# KeyMicAP starts at position snonce_end + 1
keymic_ap_start = snonce_end + 1
# KeyMicAP is 32 chars
keymic_ap_end = keymic_ap_start + 32
keymic_ap = line[keymic_ap_start:keymic_ap_end]
print("KeyMicAP: %s" % keymic_ap)

# KeyMicSTA starts at position keymic_ap_end + 1
keymic_sta_start = keymic_ap_end + 1
# KeyMicSTA is 32 chars
keymic_sta_end = keymic_sta_start + 32
keymic_sta = line[keymic_sta_start:keymic_sta_end]
print("KeyMicSTA: %s" % keymic_sta)

# EKeyAP starts at position keymic_sta_end + 1
ekey_ap_start = keymic_sta_end + 1
# EKeyAP is 32 chars
ekey_ap_end = ekey_ap_start + 32
ekey_ap = line[ekey_ap_start:ekey_ap_end]
print("EKeyAP: %s" % ekey_ap)

# EKeySTA starts at position ekey_ap_end + 1
ekey_sta_start = ekey_ap_end + 1
# EKeySTA is 32 chars
ekey_sta_end = ekey_sta_start + 32
ekey_sta = line[ekey_sta_start:ekey_sta_end]
print("EKeySTA: %s" % ekey_sta)

# Verify the hash line
hash_line = "%s:%s:%s:%s:%s:%s:%s:%s:%s" % (
    essid, ap, sta, anonce, snonce,
    keymic_ap, keymic_sta, ekey_ap, ekey_sta
)
print()
print("Hash line:", hash_line)
print("Match:", hash_line == line)
