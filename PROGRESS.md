# WiFi Cracker Progress

## 📌 全局規則（一直有效）
1. **遇到問題可以找 `subagent_codex` 幫忙** — 全局套用。任何卡住（Mac 驅動、抓包 0 幀、SIP/kext、hashcat 參數…）都可以直接丟給 Codex 子代理診斷/解，不必先問。
1b. **調 codex 省 token**：給 `subagent_codex` 的 prompt 只放**核心任務目標 + 必要的關鍵限制**，剔除所有無用廢話/背景鋪陳。
2. **GPT 模型規則**：任何 GPT 調用一律限 **gpt5.6**（`subagent_codex` → `gpt-5.6-terra`，已實測確認）。**嚴禁 `gpt-6-astra`**，除非用戶主動要求。子代理讀的是 `~/.dsh/codex-subagent-terra/config.toml`（model=gpt-5.6-terra），**別動** `~/.codex/config.toml`（那是日常 Codex = gpt-6-astra）。
3. **報告用中文**；用戶常不在，**盡量少用 ask_user_question 彈窗**，能自主決定就自主決定。

## 🎯 目標
破解 **32H10F** — WPA2 Personal, 5GHz。
⚠️ **頻道 56 只是猜測，尚未證實**（附近有兩個 ch56 AP -62/-57 dBm，BSSID 未 disambiguate）。
交付物 = **可攜式 Mac 抓包裝置**：Mac GUI 選目標 → 自動抓包（monitor + 鎖頻道 + 抓 handshake）→ 自動回傳 hash 給 Windows。**不依賴 agent 手動 SSH**。

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
  - **RT5572 USB NIC** (Ralink, 真 USB ID **`2001:3c1a`**, 未 device-verified) → **macOS 無 WiFi 驅動** → 直接抓不了。
  - en0 是 SSH 命脈 → 盡量別動它（LAN 下 ~3s blip 可接受）。
  - **⚠️ 2026-09-10 更正：en3/en4 不是 RT5572！** 它們是 Mac 自己的 **`AppleT8112USBXDCI` NCM「Mac」虛擬裝置**（vendorID=1452/productID=6405, MAC 56:5c:fb 是 Apple OUI, USB-C 埠對接）。完整 `ioreg -l` dump（30089 行）裡**沒有 D-Link / RT5572 / 0x3c1a 任何字串** → **DWA-160 現在可能根本沒插在 Mac 上**（HS 埠 ConnectCount=385 + 3 次 enumeration failure，插過很多次）。USB 卡要處理前先確認它物理插入。

### ✅ 現行路線（2026-09-08 轉向）：AirSnare 抓 en0（比 VM 簡單）
**核心洞察**：macOS 上 monitor mode 與 managed/associated 模式**互斥**（同一介面不能同時）。所以流程 = **抓(in monitor) → 退出 monitor → en0 重連家 32H9F → 送 hash**。
- **AirSnare**（`rtulke/airsnare`，前 zizzania）= 現代 macOS（DriverKit Broadcom）唯一可靠 monitor 抓包工具。
  - 安裝（已装 ✅）：`brew tap rtulke/airsnare && brew trust rtulke/airsnare && brew install airsnare`（v0.10.0，Rust，需 CLT 26.x）。**已装好 CLT 26.6 + AirSnare 0.10.0**。
  - 用法（**已實測**）：`sudo env SUDO_UID=501 SUDO_GID=20 /opt/homebrew/bin/airsnare -i en0 -c <ch> -n -g -w /tmp/air.pcap &`
    - `-n` = 被動等 handshake；`-g` = 連 beacon 一起 dump；`-c` 鎖頻道；`-d <count>` 可發 deauth 強迫握手。
    - **SUDO_UID 陷阱（實測）**：若外包 `sudo nohup` 腳本，airsnare 看到 `SUDO_UID=0` 會直接死 `[!] Invalid SUDO_UID '0'` → 一定要 `sudo env SUDO_UID=501`。
    - macOS 沒有 GNU `timeout` → 背景跑 + `kill`。
  - **關鍵：AirSnare 要 en0 先 disassociate**（CoreWLAN 在已關聯時拒絕鎖頻道）。
- **✅ 2026-09-10 實測確認：AirSnare 抓得到 beacon（v3 驗證）**：ch9 被動 30 秒抓到 **10 個 802.11 beacon**（含家 32H9F -43dBm、鄰居 PK HOUSE/LilyKuma_cht/NiuPu/cc710206/Paige + 3 個隱藏 SSID，ch8/ch9）。pcap 4371 bytes，tcpdump 可正常解。**AirSnare-on-en0 路線成立**（beacon 已證實；4-way handshake 待目標有人上線或 deauth）。
- **穩健重連（治 -3900）**：`sudo ifconfig en0 down; sleep2; up; sleep2; networksetup -setairportpower en0 off; sleep2; on; sleep3; networksetup -setairportnetwork en0 32H9F` → 輪詢 `ipconfig getifaddr en0` 直到有 IP。
- 待抓：`hcxpcapngtool -o /tmp/hash.hc22000 /tmp/air_cap.pcapng`（m=22000）→ SFTP → Windows:8766 `/api/receive-hash`。
- **QEMU VM + RT5572 USB passthrough** = **fallback，且是「不斷線」路線（codex 判定，2026-09-08）**：
  - **RT5572 = D-Link DWA-160 B2，雙頻 2.4 + 5 GHz** → 看得見 5GHz 目標 ✅。
  - 原生 macOS 26 arm64 **無 monitor 版 WiFi 驅動**（卸 NCM patcher 也救不了）。
  - Linux `rt2800usb` **支援 `2001:3c1a`**，含 5GHz + monitor mode → **VM 可行**。
  - **⚠️ passthrough 要傳 `2001:3c1a`（RT5572 本體），不是 `05ac:1905`（USB-C 埠）** — 舊 QEMU 指令傳錯設備。
  - 優點：USB 卡獨立抓包 → **en0 專職 32H9F/SSH，Mac 不斷線**（最符合 portable device 目標）。

### 🔴 目前卡住：VM 映像下載 + serial console
- **Mac 網路坑（2026-09-10 實測）**：Mac 上 `curl cloud-images.ubuntu.com` **DNS 解不到**；`brew install --head libusb` **portable-ruby 更新失敗**（Mac 到 GitHub 受限）→ **大檔案改在 Windows 下載再 SCP 過去**。
- 要看 VM 內 USB enumeration + RT5572 綁定，唯一途徑是 **serial console**。但：
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
| `tcpdump -I en0` (AirJack 式) | ⚠️ DriverKit Broadcom 只給 **promisc 非 monitor** → 0 幀（ifconfig 無 monitor flag）|
| CoreWLAN `monitorMode` (pyobjc) | ⚠️ **read-only**，`iface.monitorMode=True` 報 read-only，無 `setMonitorMode_` |
| `tcpdump -i en0 -y IEEE802_11_RADIO` (managed) | ⚠️ "IEEE802_11_RADIO is not one of the DLTs supported"（managed 用別 DLT）|
| en0 抓完卡 monitor | ⚠️ `setairportnetwork` 回 **-3900**（介面忙碌）→ 先 `ifconfig down/up`+`airportpower off/on` 再重連 |

### 背景任務
- **hunt4 poller** (PID 4536)：10h loop, ping sweep + ARP diff；Mac UP 時寫 `IP.txt`、dump state、sftp 複製 `/tmp/cap.pcapng`+`hash.hc22000`、跑 hcxpcapngtool；log `C:\wifi-crack\mac_capture\poll.log`。已 fire 過一次（.125）。
- **crack runner** (PID 16260)：⚠️ **已過期**（"NO HASH after 60 min"）→ hash 出現後要重啟。
- 目前 `C:\wifi-crack\mac_capture\` 仍**沒有 hash.hc22000 / cap.pcapng**（舊 hash 是舊目標 32H9F_5G 的，失效）。

### 下一步 (TODO)
1. [ ] 下載 jammy aarch64 cloud → 解 /boot/vmlinuz + initrd + 取得 root UUID
2. [ ] QEMU `-kernel/-initrd + console=ttyAMA0 + USB passthrough`（**傳 `2001:3c1a`**，不是 05ac:1905）啟動 → 拿到 serial console
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
