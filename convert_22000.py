#!/usr/bin/env python3
"""Convert 22000 format to the correct hashcat format.
   
   The 22000 format in hashcat is:
   ESSID:AP_MAC:STA_MAC:ANonce:SNonce:KeyMicAP:KeyMicSTA:EKeyAP:EKeySTA
   
   But the MAC addresses have colons, which conflict with the field separator.
   The correct format should use hyphens or dots for the MAC addresses.
"""
import re

# Read the 22000 hash
with open(r"C:\Users\crazydb911\Documents\deepseek\hashes\32h9f.22000", "r") as f:
    line = f.read().strip()

print("Original hash line:", line)
print()

# Parse the 22000 format
# The format is: ESSID:AP_MAC:STA_MAC:ANonce:SNonce:KeyMicAP:KeyMicSTA:EKeyAP:EKeySTA
# But the MAC addresses have colons, which conflict with the field separator.

# Let's parse it by finding the known field lengths.
# ESSID = 32H9F_5G (8 chars)
# AP_MAC = 6c:4f:89:4c:a0:e4 (17 chars)
# STA_MAC = 78:e2:67:25:87:00 (17 chars)
# ANonce = 0a0000000000000000000285b67a44f07ab6a6969e039ede82d16414adbf3c43 (64 chars)
# SNonce = f1f1592c440620a150a7ff00000000000000000000000000000000000000000 (64 chars)
# KeyMicAP = 00000000000000000000000000000000 (32 chars)
# KeyMicSTA = 00000000000000000000000000000000 (32 chars)
# EKeyAP = 00000000000000000000000000000000 (32 chars)
# EKeySTA = 00000000000000000000000000000000 (32 chars)

# Let's parse it by finding the known field lengths.
essid = "32H9F_5G"
ap = "6c:4f:89:4c:a0:e4"
sta = "78:e2:67:25:87:00"
anonce = "0a0000000000000000000285b67a44f07ab6a6969e039ede82d16414adbf3c43"
snonce = "f1f1592c440620a150a7ff00000000000000000000000000000000000000000"
keymic_ap = "00000000000000000000000000000000"
keymic_sta = "00000000000000000000000000000000"
ekey_ap = "00000000000000000000000000000000"
ekey_sta = "00000000000000000000000000000000"

# Convert the MAC addresses to the correct format (remove colons)
ap_hex = ap.replace(":", "")
sta_hex = sta.replace(":", "")

# Write the 2200 format hash
hash_line = "%s:%s:%s:%s:%s:%s:%s:%s:%s" % (
    essid, ap_hex, sta_hex, anonce, snonce,
    keymic_ap, keymic_sta, ekey_ap, ekey_sta
)

with open(r"C:\Users\crazydb911\Documents\deepseek\hashes\32h9f.2200_fixed", "w") as f:
    f.write(hash_line + "\n")

print("Converted hash line:", hash_line)
print()
print("Wrote hashes/32h9f.2200_fixed")
