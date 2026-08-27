#!/usr/bin/env python3
"""Fix the ESSID in the hash file."""

def main():
    hash_file = "C:/Users/crazydb911/Documents/deepseek/32h9f_eapol_nas.hc22000"
    output_file = "C:/Users/crazydb911/Documents/deepseek/32h9f_eapol_fixed.hc22000"
    
    # Correct SSID hex
    ssid = "32H9F_5G"
    ssid_hex = ssid.encode('utf-8').hex()
    print(f"Correct SSID: {ssid} -> {ssid_hex}")
    
    with open(hash_file) as f:
        lines = [l.strip() for l in f if l.strip()]
    
    print(f"Total hashes: {len(lines)}")
    
    fixed = []
    for line in lines:
        tokens = line.split('*')
        # Replace token 5 (ESSID)
        old_essid = tokens[5]
        tokens[5] = ssid_hex
        fixed_line = '*'.join(tokens)
        fixed.append(fixed_line)
        print(f"  {old_essid} -> {ssid_hex}")
    
    with open(output_file, 'w') as f:
        for line in fixed:
            f.write(line + '\n')
    
    print(f"\nSaved to {output_file}")

if __name__ == '__main__':
    main()
