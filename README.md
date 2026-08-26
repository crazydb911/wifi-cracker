# WiFi Cracker - Mac + Windows

Two-end WiFi cracking system: capture on Mac, crack on Windows (RTX 4090).

## Architecture

```
Mac (port 8765)                    Windows (port 8766)
┌─────────────────┐                ┌─────────────────────┐
│ 1. Scan (tshark)│                │ 1. Receive pcap     │
│ 2. Capture      │──upload──────> │ 2. Extract (scapy)  │
│ 3. Upload       │                │ 3. Crack (hashcat)  │
│ 4. Poll status  │<──poll────────│ 4. GPU monitor      │
└─────────────────┘                └─────────────────────┘
```

## Features

### Mac App (mac_wifi_cracker_v6.py)
- **Scan**: tshark monitor mode WiFi scan
- **Capture**: Select AP, choose duration, one-click capture
- **Upload**: One-click upload to Windows (auto extract + crack)
- **Windows Status**: Poll Windows crack progress/results

### Windows App (windows_cracker_app.py)
- **Upload & Extract**: Upload pcap → auto scapy extract 22000 hashes
- **Crack**: 3 modes (straight / hybrid / mask) + wordlists + rules
- **GPU Monitor**: Real-time temp/util with thermal management
- **Thermal Control**: Adjustable temp limit, auto throttle, critical abort
- **Live Log**: Hashcat output in real-time
- **Results**: Crack results display

## Setup

### Mac
```bash
# Requirements
brew install wireshark  # for tshark
pip3 install fastapi uvicorn requests scapy

# Run
python3 mac_wifi_cracker_v6.py
# Visit http://<mac-ip>:8765
```

### Windows
```powershell
# Requirements
# - hashcat 7.1.2 at C:\tools\hashcat-7.1.2
# - Wordlists at C:\wifi-crack\wordlists\
# - nvidia-smi in PATH

# Run
python windows_cracker_app.py
# Visit http://<windows-ip>:8766
```

## Usage

1. **Mac**: Scan → Select AP → Capture → Upload
2. **Windows**: Auto-receive → Extract → Crack (with thermal control)
3. **Mac**: Poll Windows for results

## Hash Format (hashcat -m 22000)

```
WPA*02*<KEYMIC>*<AP_MAC>*<STA_MAC>*<SSID_HEX>*<ANONCE>*<EAPOL_FRAME>*03
```

## Thermal Management

| Temp | Status | Action |
|------|--------|--------|
| < 75°C | Normal | Full speed |
| 75-85°C | Warning | Throttle (pause 10s) |
| > 92°C | Critical | Abort |

Adjustable via UI slider (70-95°C).

## Files

| File | Description |
|------|-------------|
| `mac_wifi_cracker_v6.py` | Mac capture app (port 8765) |
| `windows_cracker_app.py` | Windows crack app (port 8766) |
| `mac_deploy_v6.py` | Deploy Mac app via SSH |
| `extract_final3.py` | Standalone hash extractor |
| `32h9f_eapol.pcapng` | Sample capture |
| `32h9f_eapol_fixed.hc22000` | Extracted hashes |
