#!/usr/bin/env python3
"""Verify the 22000 hash structure token by token."""
import sys

def main():
    hash_file = sys.argv[1] if len(sys.argv) > 1 else "32h9f_eapol_nas.hc22000"
    
    with open(hash_file) as f:
        lines = [l.strip() for l in f if l.strip()]
    
    print(f"Total hashes: {len(lines)}")
    print()
    
    for i, line in enumerate(lines[:3]):  # First 3 hashes
        tokens = line.split('*')
        print(f"=== Hash {i+1} ({len(tokens)} tokens) ===")
        
        expected = ['WPA', '02', 'keymic', 'apmac', 'stamac', 'essid', 'anonce', 'eapol', '03']
        for j, (tok, exp) in enumerate(zip(tokens, expected)):
            print(f"  Token {j} ({exp}): {tok[:80]}{'...' if len(tok) > 80 else ''} ({len(tok)} chars)")
        
        # Verify specific tokens
        print(f"\n  --- Verification ---")
        print(f"  Token 0 (WPA): {tokens[0]} {'✓' if tokens[0] == 'WPA' else '✗'}")
        print(f"  Token 1 (02): {tokens[1]} {'✓' if tokens[1] == '02' else '✗'}")
        print(f"  Token 2 (keymic 32hex): {len(tokens[2])} chars {'✓' if len(tokens[2]) == 32 else '✗'}")
        print(f"  Token 3 (apmac 12hex): {len(tokens[3])} chars {'✓' if len(tokens[3]) == 12 else '✗'}")
        print(f"  Token 4 (stamac 12hex): {len(tokens[4])} chars {'✓' if len(tokens[4]) == 12 else '✗'}")
        print(f"  Token 5 (essid): {tokens[5]} (hex of SSID)")
        ssid_hex = tokens[5]
        ssid = bytes.fromhex(ssid_hex).decode('utf-8', errors='replace')
        print(f"         -> SSID: {ssid}")
        print(f"  Token 6 (anonce 64hex): {len(tokens[6])} chars {'✓' if len(tokens[6]) == 64 else '✗'}")
        print(f"  Token 7 (eapol frame): {len(tokens[7])} chars")
        print(f"  Token 8 (msg_num): {tokens[8]} {'✓' if tokens[8] in ['01', '03'] else '✗'}")
        print()

if __name__ == '__main__':
    main()
