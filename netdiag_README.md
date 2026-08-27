# WiFi Cracker - 32H9F_5G

WPA2 4-way handshake capture & crack project for network `32H9F_5G`.

## Target
| Field | Value |
|-------|-------|
| SSID | 32H9F_5G |
| BSSID | 6C:4F:89:4C:A0:E4 |
| Band | 5GHz |
| Channel | 56 |
| Width | 80MHz |

## Hosts
| Host | IP | Role |
|------|----|----|
| Mac | 192.168.1.102 | WiFi capture (monitor mode) |
| Windows | 192.168.1.107 | Hashcat (choco) |
| NAS | 192.168.1.115 | Storage + hcxtools build |

## Tools
- **hcxtools v7.1.2** (ZerBea/hcxtools) - built on Mac, `hcxpcapngtool`
- **hashcat** (Windows, choco)
- **aircrack-ng 1.7_2** (Mac, Homebrew)
- **tshark / Wireshark 4.6.8** (Mac, Homebrew)

## Status
- [x] Mac monitor mode capture (mac_all.cap, 163MB)
- [x] EAPOL extraction (tshark -> 32h9f_eapol.pcapng, 19KB)
- [x] 4-way handshake verified: M1=3, M2=3, M3=3, M4=3
- [ ] hcxpcapngtool hash extraction (ANONCE/SNONCE showing 0000...)
- [ ] Hashcat crack

## Key Files
- `captures/mac_all.cap` - Full capture (163MB, git-lfs)
- `captures/32h9f_eapol.pcapng` - EAPOL only (19KB)
- `hashes/32h9f.22000` - Hashcat mode 22000 hash
- `tools/hcxtools-7.1.2/` - Source (built on Mac)
- `scripts/` - Capture & extraction scripts
