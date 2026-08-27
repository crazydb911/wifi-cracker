# WiFi Cracker Progress

## Status: EAPOL Capture Blocked

### Working
- ✅ Windows app (port 8766): extract + crack + LAN control
- ✅ Mac app v6 (port 8765): scan + capture + upload
- ✅ Mac → Windows upload pipeline
- ✅ Windows LAN endpoints: `/api/log`, `/api/pcaps`, `/api/crack_wordlist`
- ✅ File logging (both ends)

### EAPOL Capture Attempts (15 methods, all 0 EAPOL from 32H9F_5G)
| Method | Result |
|--------|--------|
| 1. `setairportpower off 8s/on` | 0 EAPOL, Mac not auto-reconnect |
| 2. `setairportpower off 15s/on` | 0 EAPOL |
| 3. `ifconfig down/up` + power | 0 EAPOL |
| 4. `airport -z` + `ifconfig` + power | 0 EAPOL |
| 5. `setairportpower off 10s/on` + `setairportnetwork` | 0 EAPOL, "Could not find network" |
| 6. `setairportpower off 15s/on` + 30s wait + connect | 0 EAPOL |
| 7. `wdutil scan` + connect | 0 EAPOL, wdutil syntax wrong |
| 8. `osascript` GUI click | 0 EAPOL, SystemUIServer menu not found |
| 9. `kill dhclient` + `setairportnetwork` | 0 EAPOL, still connected (no re-auth) |
| 10. `sudo setairportnetwork` | 2 EAPOL (OTHER AP, not 32H9F_5G) |
| 11. `airport -m` monitor mode | 0 EAPOL, no mon0 interface created |
| 12. `ifconfig down/up` (radio stays on) | 0 EAPOL, Mac not re-associate |
| 13. `removeallknownnetworks` + power off/on | 0 EAPOL, wrong command |
| 14. `removepreferredwirelessnetwork` + power off/on | 0 EAPOL, "Could not find network" |
| 15. `airport --setpower 0/1` | Mac offline, no EAPOL |

### Root Cause
Mac's `setairportpower off/on` does NOT force re-association. The Mac thinks it's still connected to 32H9F_5G (shows "Current Wi-Fi Network: 32H9F_5G") but doesn't actually re-authenticate. The EAPOL frames captured are from OTHER APs on the network.

### Next Steps
1. **Manual test**: User manually disconnects → reconnects while tshark captures
2. **Try `networksetup -removeallpreferredwirelessnetworks`** (correct command)
3. **Try `sudo ifconfig en0 promisc`** before capture (might capture more frames)
4. **Try `sudo ifconfig en0 down; sleep 10; sudo ifconfig en0 up`** (longer wait)
5. **Try `sudo ifconfig en0 alias 192.168.1.102`** (force IP)
6. **Try `sudo airport en0 --disassociate`** (if exists)

### Files
- Mac: `C:\Users\crazydb911\Documents\deepseek\mac_wifi_cracker_v6.py`
- Windows: `C:\Users\crazydb911\Documents\deepseek\windows_cracker_app.py`
- GitHub: `https://github.com/crazydb911/wifi-cracker` (last push: `14c728a`)

### Hashcat
- Wordlists: `rockyou` (490), `wifi_wordlist` (175K)
- All previous attacks: 0/6 hashes (truncated nonces)
- Need fresh capture with complete nonces
