# Android WiFi Monitor Capture → Hashcat 22000

Crack a WPA2/WPA3 network from a **rooted Android phone** used as a monitor-mode
capture device, feeding extracted 22000 hashes to the Windows RTX-4090 hashcat
cracker (`windows_cracker_app.py`, port 8766).

## Target (validated)

| field | value |
|---|---|
| SSID | `32H10F` |
| vendor | Xiaomi (Qualcomm single phy0, 2.4+5G combo chip, NO phy1) |
| 2.4G BSSID #1 | `bc:3e:07:01:dc:98` — **ch1 / 2412 MHz** |
| 2.4G BSSID #2 | `bc:3e:07:01:dc:92` — **also ch1 / 2.4G** (second SSID, NOT 5G) |
| 5G | none observed — `dc:92` is a second 2.4G BSSID, not a 5G radio |

> Corrected this session: `dc:92` was earlier assumed to be a "5G twin". Raw-MAC
> byte search of the captures shows `dc:92` present in **every ch1 (2.4G) capture**
> and **absent from every 5G sweep**. It is a second 2.4G BSSID on ch1. The 5G
> chase was a red herring.

## Capture device

Xiaomi 11T (thyme), Android 13, **rooted** (`su` = `/system/bin/su`, uid 0).
Serial `24d165c4`. ADB over USB from the Windows box.

Qualcomm vendor driver: standard `iw dev wlan0 set type monitor` is rejected
(`EOPNOTSUPP -95`). Monitor mode is a **vendor sysfs toggle**:

```sh
echo 4 > /sys/module/wlan/parameters/con_mode   # 4 = functional monitor
echo 0 > /sys/module/wlan/parameters/con_mode   # restore managed
```

### Soft reset (re-init without reboot)

After a 5G tune the interface wedges (`set freq` → `EBUSY`). Reliable recovery is
a **con_mode 0→4 toggle**, which re-initializes the driver:

```sh
pkill -9 tcpdump                       # a leftover tcpdump causes EBUSY
ip link set wlan0 down
echo 0 > /sys/module/wlan/parameters/con_mode
echo 4 > /sys/module/wlan/parameters/con_mode
ip link set wlan0 up
iw dev wlan0 set freq 2412             # 2.4G  (or: set freq <mhz> HT20 for 5G)
```

`set freq <mhz> HT20` (token form) works per 5G channel on this `iw`; a numeric
bandwidth (`set freq <mhz> 80`) is rejected.

## Files

| file | what it is |
|---|---|
| `android_deauth.c` / `deauth_aarch64` | AF_PACKET deauth injector. **FC = 0x00b0** (mgmt subtype 11 = deauth). Was wrongly 0x0030 (reassoc-response) → storms ineffective. |
| `android_probe.c` / `probe_aarch64` | probe-request injector. **FC = 0x0070** (subtype 7). Reads host MAC via `SIOCGIFHWADDR`. |
| `deauth_aarch64` / `probe_aarch64` | aarch64 static ELF built with zig — run directly on Android Bionic. |
| `deep_scan.py` | Windows-side pcap analyzer (frame-type + EAPOL + PMKID). |
| `scripts/target.sh` | **targeted capture**: BPF-filtered to a BSSID set + deauth/probe loop. |
| `scripts/target_filter.txt` | BPF `ether host …` list for `target.sh`. |
| `scripts/sweep5g3.sh` | 5G probe-injection sweep (UNII-1/3). |
| `scripts/sweep2g.sh` | 2.4G ch1/6/11 sweep. |
| `scripts/capG.sh` / `capLong.sh` | dense 90 s / moderate 10 min deauth-storm captures. |
| `scripts/openssl_stubs.c` | dummy OpenSSL bodies so `hcxpcapngtool` links+runs on aarch64 (see build). |

### On-phone toolchain (`/data/local/tmp/`)
`deauth`, `probe`, `hcxpcapngtool`, and the `*.sh` scripts. All pushed via
`MSYS_NO_PATHCONV=1 adb -s 24d165c4 push …` (Windows path form — MSYS path
conversion breaks adb on leading-`/` paths).

## 802.11 frame facts (corrected)

- mgmt frame: `FC(2) | DA(6) | SA(6) | BSSID(6) | body`
- subtypes: 0=auth, 4=disassoc, 5=assoc_req, 6=assoc_resp, 7=probe_req,
  8=probe_resp, **9=beacon**, 11=deauth.
- deauth: FC `0x00b0`, DA=client/broadcast, SA=AP, BSSID=AP, seq `0000`,
  reason `0200` (26 bytes).
- EAPOL: detect by EtherType `0x888e` in the payload, **validate** `key_info`
  ∈ {M1 0x8001/0x0001, M2 0x4401, M3 0x2001, M4 0x1401}. A bare
  `rec.find(b'\x88\x8e')` gives false positives from QoS-data payloads.
- The phone's PPI header is variable-length; the 802.11 FC does **not** sit at
  the raw `pph_len` offset. EAPOL detection (whole-record EtherType scan) is
  offset-independent and reliable; FC-based subtype counting is not.

## hcxpcapngtool on aarch64

```sh
ZIG="C:/temp/zigd/zig-windows-x86_64-0.14.0/zig.exe"
"$ZIG" cc -target aarch64-linux-musl -O2 -static \
  -DOPENSSL_CONFIGURED_API=30000 -DVERSION_TAG='"7.1.2"' -DVERSION_YEAR='"2023"' \
  -I hcxtools-7.1.2 -I /c/temp/openssl_inc/include \
  hcxpcapngtool.c /c/temp/openssl_stubs.c -o hcxpcapngtool_aarch64
```

`openssl_stubs.c` supplies dummy bodies for the OpenSSL symbols hcxpcapngtool
links but only calls during its (unused-on-our-path) candidate check. Non-NULL
sentinels are required: `EVP_MD_CTX_new→(…*)0x1`, `EVP_MAC_fetch→(…*)0x1`,
`EVP_MAC_CTX_new→(…*)0x1`. On the phone:

```sh
/data/local/tmp/hcxpcapngtool --all -o out.22000 cap.pcap   # or -o cap.hc22000 cap.pcap
```

## Status / findings

- **2.4G (both BSSIDs, ch1) is the only productive band and is highly resistant**:
  clients use PMKSA fast-reauth on deauth; the AP does **not** expose PMKID in
  probe responses (clientless attack confirmed dead); even a dense 90 s broadcast
  deauth storm yields **0 real EAPOL** frames. PMF (802.11w) is OFF, so deauths
  are valid — the resistance is PMKSA caching, not signed management frames.
- **Open goal**: capture a full EAPOL M1+M2 (or M3+M4) pair from either BSSID,
  or a PMKID. Best remaining lever: a long patient capture that catches a natural
  full-reauth event (new client / PMKID expiry / AP reboot). `capLong.sh` runs a
  10 min moderate-storm for exactly this.