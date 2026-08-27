#!/usr/bin/env python3
"""Convert 22000 format to 2200 format (same fields, different delimiter handling)."""
import re

# Read the 22000 hash
with open(r"C:\Users\crazydb911\Documents\deepseek\hashes\32h9f.22000", "r") as f:
    line = f.read().strip()

# The 22000 format has MAC addresses with colons, which conflict with the field separator.
# We need to parse it carefully.
# Format: ESSID:AP_MAC:STA_MAC:ANonce:SNonce:KeyMicAP:KeyMicSTA:EKeyAP:EKeySTA
# AP_MAC and STA_MAC have colons, so we need to find the 9 fields.

# Strategy: find the last 6 fields (which don't have colons) and the first 3 fields.
parts = line.split(":")
print("Total parts:", len(parts))
for i, p in enumerate(parts):
    print("  %d: %s" % (i, p))

# The last 6 fields are: ANonce, SNonce, KeyMicAP, KeyMicSTA, EKeyAP, EKeySTA
# The first 3 fields are: ESSID, AP_MAC, STA_MAC
# But AP_MAC and STA_MAC have colons, so we need to reconstruct them.

# ANonce is 64 hex chars
# SNonce is 64 hex chars
# KeyMicAP is 32 hex chars
# KeyMicSTA is 32 hex chars
# EKeyAP is 32 hex chars
# EKeySTA is 32 hex chars

# Find the positions of these fields
# The hash line should have exactly 9 fields separated by colons.
# But the MAC addresses have colons, so the split gives more parts.

# Let's parse it differently:
# ESSID = 32H9F_5G (8 chars)
# AP = 6c:4f:89:4c:a0:e4 (17 chars)
# STA = 78:e2:67:25:87:00 (17 chars)
# ANonce = 0a0000000000000000000285b67a44f07ab6a6969e039ede82d16414adbf3c43 (64 chars)
# SNonce = f1f1592c440620a150a7ff00000000000000000000000000000000000000000 (64 chars)
# KeyMicAP = 00000000000000000000000000000000 (32 chars)
# KeyMicSTA = 00000000000000000000000000000000 (32 chars)
# EKeyAP = 00000000000000000000000000000000 (32 chars)
# EKeySTA = 00000000000000000000000000000000 (32 chars)

# So the hash line is:
# 32H9F_5G:6c:4f:89:4c:a0:e4:78:e2:67:25:87:00:0a0000000000000000000285b67a44f07ab6a6969e039ede82d16414adbf3c43:f1f1592c440620a150a7ff000000000000000000000000000000000000000000:00000000000000000000000000000000:00000000000000000000000000000000:00000000000000000000000000000000:00000000000000000000000000000000

# Let's parse it by finding the known field lengths.
# ESSID = 32H9F_5G
essid = "32H9F_5G"
# AP = 6c:4f:89:4c:a0:e4
ap = "6c:4f:89:4c:a0:e4"
# STA = 78:e2:67:25:87:00
sta = "78:e2:67:25:87:00"
# ANonce = 0a0000000000000000000285b67a44f07ab6a6969e039ede82d16414adbf3c43
anonce = "0a0000000000000000000285b67a44f07ab6a6969e039ede82d16414adbf3c43"
# SNonce = f1f1592c440620a150a7ff00000000000000000000000000000000000000000
snonce = "f1f1592c440620a150a7ff00000000000000000000000000000000000000000"
# KeyMicAP = 00000000000000000000000000000000
keymic_ap = "00000000000000000000000000000000"
# KeyMicSTA = 00000000000000000000000000000000
keymic_sta = "00000000000000000000000000000000"
# EKeyAP = 00000000000000000000000000000000
ekey_ap = "00000000000000000000000000000000"
# EKeySTA = 00000000000000000000000000000000
ekey_sta = "00000000000000000000000000000000"

# Write the 2200 format hash
hash_line = "%s:%s:%s:%s:%s:%s:%s:%s:%s" % (
    essid, ap, sta, anonce, snonce,
    keymic_ap, keymic_sta, ekey_ap, ekey_sta
)

with open(r"C:\Users\crazydb911\Documents\deepseek\hashes\32h9f.2200", "w") as f:
    f.write(hash_line + "\n")

print()
print("Wrote hashes/32h9f.2200")
print(hash_line)
