# WiFi Cracker Progress

## 🎯 目標
破解 **32H10F** — WPA2 Personal, 5GHz, 頻道 56 (80MHz)。
附近有兩個 ch56 AP（-62 / -57 dBm），BSSID 尚未 disambiguate。

## 🏗 管線 (two-machine)
```
Mac 抓 EAPOL (monitor mode)  →  hcxpcapngtool  →  .hc22000 (m=22000 hash)
   →  SFTP 到 Windows  →  RTX 4090 hashcat (cracker app API, port 8766 @192.168.1.107)
```
- **Windows cracker**: `windows_cracker_app.py` (port 8766)。POST `/api/receive-hash {hash,ssid,bssid}` → 存 hash + 自動開跑；詞表階梯 wifi_wordlist → +best66 → rockyou+best66 → hybrid。
- **Mac capture**: 需要一個能進 **monitor mode** 的**第二個** WiFi 介面。

## ⏱ 2026-09-08 目前進度快照 (32H10F)

### 已確認
- ✅ macOS **managed mode 的 en0 抓不到 EAPOL**：macOS 802.1X supplicant 在 BPF 之前就把 EAPOL 吃掉了 → 光靠 en0 不夠。
- ✅ Mac 介面拓撲：
  - **en0** = 唯一 WiFi + SSH + 預設路徑 (Broadcom BCM4387, 74:a6:cd:bd:43:f2)。
  - **RT5572 USB NIC** (Ralink, 真 USB ID **`2001:3c1a`**) → 在 macOS 上被 `AppleUSBRealtek8153Patcher.kext` 呈現為 **USB 網卡 NCM (en3/en4)**，不是 WiFi 介面 → **macOS 直接抓不了**。
  - en0 是 SSH 命脈 → 盡量別動它（LAN 下 ~3s blip 可接受）。

### 已選路線
**QEMU aarch64 Linux VM + RT5572 USB passthrough**（不重啟 Mac、保 SSH 活著）
- 驅動 = **rt2800usb**（Linux kernel 內建），支援 monitor mode + frame injection + 5GHz。
- 已知坑：有些 kernel 上 `rt2800usb` 載入後**不出 wlan 介面**（"RT5572 in lsusb but not iwconfig"）→ 需在 VM 內用 `lsusb`+`dmesg`+`iwconfig` 驗證綁定。
- **NCM 兩難（未解）**：RT5572 在 Mac 上是 NCM/RTL8153。在 Linux 可能綁成 (a) 原生 Ralink WiFi (`rt2800usb`→wlan0, 可 monitor) 或 (b) USB-ethernet (`r8152`/`cdc_ncm`, 不能 monitor)。**只有進 VM 看 `lsusb`+`dmesg` 才知答案。**
- QEMU usb-host on aarch64 virt 需顯式 xHCI：`-device qemu-xhci,id=xhci` 再 `-device usb-host,vendorid=0x05ac,productid=0x1905`（0x05AC:0x1905 = Mac USB-C DRD port，usb-host 抓它才能到下游 RT5572）。

### 🔴 目前卡住：VM 無法開 serial console
要看 VM 內 USB enumeration + RT5572 綁定，唯一途徑是 **serial console**。但：
- QEMU `-nographic -serial file:` → serial.log 0 bytes（`-nographic` 把 serial0 掛到 mux，多給的 `-serial` 變成沒用的 serial1）。改 `-display none -monitor none -serial file:` → 還是靜音（kernel 沒有匹配的 `console=`）。
- 想改用 **explicit `-kernel/-initrd/-append "console=ttyAMA0 …"`** 啟動 → 但 kernel 要從映像裡提出來。
- **Noble cloud 映像的坑**：root (ext4, UUID `f04fc0a0-a851-4173-ac9b-df0666934299`, "cloudimg-rootfs") 的 `/boot/` **沒有 vmlinuz、沒有 initrd**；GPT 只有**一個分區**（root, 2559MB, 1GB offset），**沒有獨立 ESP**。→ 這張 Noble 是 **UKI / initrdless** 啟動，kernel 是 ESP 裡的 UKI `.efi`，但 qcow2→raw 的 GPT 把 ESP 弄沒了。
- 解法（進行中）：**換一張傳統 `/boot/vmlinuz` + `/boot/initrd` 的映像** → 直接 `-kernel/-initrd + console=ttyAMA0` 啟動。已開始下載 **jammy (Ubuntu 22.04) aarch64 cloud**（kernel 5.15, rt2800usb 有 RT5572, 傳統 /boot）。

### 死路清單（別再踩）
| 方法 | 結果 |
|------|------|
| macOS managed en0 抓 EAPOL | ❌ supplicant 吃掉 EAPOL |
| macOS 直接用 RT5572 (en3/en4 NCM) | ❌ 被 kext 當 USB-ethernet，非 WiFi |
| macOS 26 **NBD** | ❌ 無 nbd.kext |
| Homebrew **libguestfs** | ❌ arm64_tahoe 無 formula |
| **hdiutil** attach raw GPT / raw ext4 | ❌ 都不行 |
| **7zz** wildcard / 目錄 spec 解 ext4 | ⚠️ `Type=Ext` 讀得到，但 `e '*vmlinuz*'` / `x 'boot/'` 解出 0 檔 → 要用完整 list + 明確路徑 |
| Noble UKI 映像 | ⚠️ /boot 空、無 ESP → 無法 `-kernel` 啟動 |
| 7zz `command not found` (SSH) | 非互動 shell PATH 無 /opt/homebrew/bin → 用全路徑 `/opt/homebrew/bin/7zz` |
| QEMU `No 'usb-bus'` | aarch64 virt 要 `-device qemu-xhci` |

### 背景任務
- **hunt4 poller** (PID 4536)：10h loop, ping sweep + ARP diff；Mac UP 時寫 `IP.txt`、dump state、sftp 複製 `/tmp/cap.pcapng`+`hash.hc22000`、跑 hcxpcapngtool；log `C:\wifi-crack\mac_capture\poll.log`。已 fire 過一次（.125）。
- **crack runner** (PID 16260)：⚠️ **已過期**（"NO HASH after 60 min"）→ hash 出現後要重啟。
- 目前 `C:\wifi-crack\mac_capture\` 仍**沒有 hash.hc22000 / cap.pcapng**（舊 hash 是舊目標 32H9F_5G 的，失效）。

### 下一步 (TODO)
1. [ ] 下載 jammy aarch64 cloud → 解 /boot/vmlinuz + initrd + 取得 root UUID
2. [ ] QEMU `-kernel/-initrd + console=ttyAMA0 + USB passthrough` 啟動 → 拿到 serial console
3. [ ] VM 內 `lsusb`+`dmesg`+`iwconfig` 確認 RT5572 綁定成 wlan0（rt2800usb）且能 monitor + 5GHz
4. [ ] `apt install aircrack-ng hcxdumptool`；hcxdumptool 抓 32H10F EAPOL
5. [ ] hcxpcapngtool → hc22000 → SFTP → 重啟 Windows crack runner
6. [ ] 回報密碼 + 更新 GitHub + commit

---

## 📜 歷史 (舊目標 32H9F_5G, 已過時)

### EAPOL Capture Attempts (15 methods, 全部 0 EAPOL)
1. `setairportpower off 8s/on` — 0, Mac 不重連
2. `setairportpower off 15s/on` — 0
3. `ifconfig down/up` + power — 0
4. `airport -z` + `ifconfig` + power — 0
5. `setairportpower off 10s/on` + `setairportnetwork` — 0, "Could not find network"
6. `setairportpower off 15s/on` + 30s + connect — 0
7. `wdutil scan` + connect — 0, 語法錯
8. `osascript` GUI click — 0
9. `kill dhclient` + `setairportnetwork` — 0
10. `sudo setairportnetwork` — 2 EAPOL (別家 AP)
11. `airport -m` monitor — 0, 無 mon0
12. `ifconfig down/up` (radio 不關) — 0
13. `removeallknownnetworks` + power — 0, 錯指令
14. `removepreferredwirelessnetwork` + power — 0
15. `airport --setpower 0/1` — Mac offline

**根因**: `setairportpower off/on` 不強迫 re-association → Mac 以為還連著 32H9F_5G 但不重驗證；抓到的 EAPOL 是別家 AP 的。

### maxTokens 截斷問題 (2026-08-28)
- 回應超 4096 tokens 被截 (`finish_reason: length`)，tool call 被靜默丟。
- 根因: `cordis.patch.yml` 的 `maxTokens: 4096` → 改 `32768`。

### Hashcat
- Wordlists: `rockyou` (490), `wifi_wordlist` (175K)。
- 舊 6 hashes: 0/6 (truncated nonces) → 需要完整 nonce 的 fresh capture。

### 環境
- Mac SSH: `tongbao`/`240628` @ 192.168.1.125; sudo pw 240628; macOS 26.6.2 arm64 (T8112, M2 Air)。
- Windows cracker: 192.168.1.107, port 8766。hashcat `C:\tools\hashcat-7.1.2` (cwd 必須是該目錄)。
- Guest login: `tongbao`, SSH key `/tmp/vmsetup/vmkey`, slirp 127.0.0.1:2222 (guest IP 10.0.2.15)。
- 有效 QEMU 啟動指令（kernel 取得後加 `-kernel/-initrd/-append`）:
  ```
  /opt/homebrew/bin/qemu-system-aarch64 -machine virt -cpu max -smp 2 -m 2048 \
    -drive file=<image>,if=virtio,format=raw \
    -drive file=/tmp/vmsetup/cidata.cdr,media=cdrom,if=virtio,format=raw,snapshot=on \
    -netdev user,id=n0,hostfwd=tcp:0.0.0.0:2222-:22 -device virtio-net-pci,netdev=n0 \
    -device qemu-xhci,id=xhci -device usb-host,vendorid=0x05ac,productid=0x1905 \
    -display none -monitor none -serial file:/tmp/vmsetup/serial.log
  ```
