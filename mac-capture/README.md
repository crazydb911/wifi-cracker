# Mac Capture Station → Hashcat 22000

Companion to `android-capture/`. Uses the **Mac** as a WiFi station/capture box
for the same target, feeding 22000 hashes to the Windows RTX-4090 hashcat
cracker (`windows_cracker_app.py`, port 8766).

## Machine

Apple Silicon **M2 Air**, macOS 26.6.2. Remote: `tongbao@192.168.1.125`,
SSH key `~/.ssh/opremote_ed25519`, **sudo password `240628`**. Home SSID
`32H9F_5G` (5G WPA3) / `32H9F` (2.4G).

Two Wi-Fi radios:
- **en0** — Apple built-in AirPort. Per-network **randomized** MAC
  (`74:a6-cd:bd:43:f2`); its WoL/magic-packet wake is **flaky** (randomized MAC
  + deeper sleep). This is the line we **disable** so it stops competing on the
  2.4G band and stops being the ambiguous primary.
- **USB Wi-Fi card (D-Link DWA-160, RTL8811AU)** — the dedicated,
  deterministic network + capture NIC. Needs the `8811au` kext loaded; if it is
  not enumerated, plug it in / load the driver first.

> Decision: run the Mac on the **USB card only** and **disable the built-in
> Wi-Fi line** (`disable_builtin_wifi.sh off`). This removes the randomized
> built-in radio from the 2.4G band and makes the DWA-160 the single NIC for
> both SSH and capture.

## Files

| file | what it is |
|---|---|
| `disable_builtin_wifi.sh` | **Disable the built-in Wi-Fi (en0)** so the Mac runs on the USB card (DWA-160) only. `off` (default) / `on` to re-enable. Warns if no active non-built-in Wi-Fi iface is present before dropping en0 (would cut SSH). |
| `wake_mac.py` | Wake-on-LAN magic packet. Default MAC = en0's built-in MAC. **After disabling the built-in, pass the DWA-160's burned-in MAC** as arg 1 (`python wake_mac.py <dwa160_mac>`). |

## Usage

```bash
# 1) Wake (while built-in is still the NIC, or after with the DWA-160 MAC):
python mac-capture/wake_mac.py [dwa160_mac]

# 2) SSH in and disable the built-in Wi-Fi line:
ssh -i ~/.ssh/opremote_ed25519 tongbao@192.168.1.125
#    (on the Mac)
SUDO_PW=240628 ./disable_builtin_wifi.sh off
```

## Notes / caveats

- **WoL MAC**: USB Wi-Fi cards support WoL only if the driver exposes it; after
  disabling the built-in, confirm the DWA-160's WoL/MAC and update `wake_mac.py`.
- **Monitor mode on macOS 26**: the classic `airport` CLI is gone; the DWA-160
  needs the `8811au` driver for reliable raw 802.11 monitor capture. The
  built-in AirPort cannot be put in monitor mode easily without that driver.
- **Capture pipeline** (once a station does an EAPOL 4-way on the target):
  pcap → `hcxpcapngtool --all -o out.22000 cap.pcap` → feed to the Windows
  cracker via `android-capture/feed_hash.py` (POST `http://127.0.0.1:8766/api/receive-hash`).

## Status

- Built-in WoL verified to wake the Mac **once** (magic packet), then went flaky
  (likely deeper sleep / randomized MAC). Physical wake is the reliable fallback.
- Open: enumerate the DWA-160 interface + confirm its kext is loaded, then run
  `disable_builtin_wifi.sh off` and validate the Mac stays reachable over the USB card.