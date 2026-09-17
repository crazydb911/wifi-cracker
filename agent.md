# AGENT.md — 核心需求與工作紀律

> 任何 agent / 新 session 接手前先讀這份 + `KNOWN_GOOD.md` + `PROGRESS.md`。

## 一、核心需求（唯一目標）
**抓到現用 WiFi `32H10F` 的密碼**（2.4G WPA2-Personal，AP BSSID `bc:3e:07:01:dc:98`，ch 1，已連線用戶端 `BC:61:93:23:BC:3F`）。
- 舊路由器的 `32H10F_5G`（BSSID `60:F8:1D:AD:01:E4`）hash 已破解完畢 = 無匹配，**不要再打它**。
- 密碼出結果前，項目未完成。

## 一之補、App 功能需求（使用者 2026-07-18 明確指定，不可省略）
**Mac 抓包 app（`mac_capture_app.py`）：**
1. 要能**顯示 USB 網卡狀態**（DWA-160 / wlan0 是否存在、驅動/firmware 是否 OK、monitor mode 狀態）。
2. 使用者**選擇想破解的 WiFi**（掃描列表）後，**一鍵處理到好**：抓包→產 .hc22000→回傳 Windows，中間不用手動操作。
3. **抓包只能用 USB 網卡**（VM 內的 wlan0），不能用 Mac 內建 Wi-Fi。
4. **過程留下完整 log**（命令、VM 狀態、結果），方便除錯與優化。
5. 成功後檔案**存名稱 + 日期**（例：`32H10F_20260718_0130.hc22000`）並**自動回傳 Windows 4090**（POST :8766）。
6. 預防無網路/回傳失敗：**可手動選擇已存的檔案，一鍵傳給 4090**（重傳）。

**Windows 破解 app（`windows_cracker_app.py`）：**
7. 收到封包後**自動開始破解**（不用手動點）。
8. **字典/攻擊順序要優化**（先高中機率、先快後慢）。
9. **過程留下完整 log**（每階段命令、進度、結果），方便除錯與優化。

## 二、管線（架構已定，不要再換）
```
Mac (tongbao@192.168.1.123)
  Alpine v3.24 aarch64 QEMU VM + DWA-160 (148f:5572) usb-host 透傳
  monitor mode + airodump-ng 抓 EAPOL（deauth 攻擊）
  hcxpcapngtool → .hc22000
        │ POST http://192.168.1.107:8766/api/receive-hash
Windows (192.168.1.107, RTX 4090)
  windows_cracker_app.py (pid 常駐 :8766) → hashcat 7.1.2 多階段
  → 回報密碼 / 無匹配
```
- Mac 端入口：`mac_capture_app.py`；Windows 端：`windows_cracker_app.py`。
- 重建 Mac VM：`mac_vm_rebuild.sh`（scp 到 Mac `/tmp/vmbuild_rebuild.sh` 後跑）。

## 三、工作紀律（防走偏）
1. **先查 KNOWN_GOOD.md §5「不要再做」清單**再動手：多階段重排、`-a 6`、把 `--backend-devices-keepfree=98` 當變更項、`-w 3`、wpa-sec、hcxdumptool 取 PMKID —— 全部已證偽。
2. **每次只改一個變量**，改完驗證（runner VM 或完整 build），再改下一個。
3. **優化建議只列清單，逐項經使用者確認才執行**；管線本身的變更（含腳本參數）先報告再動手。
4. **用中文回報**；`ask_user_question` 能不用就不用（使用者常不在）。
5. GPU 電源由使用者管理，不要開關；hashcat 階段跑完就停（溫控 90-92°C 會自動中斷，屬正常）。
6. 手機 adb（Xiaomi 11T, 24d165c4）目前不用。

## 四、環境快參
| 機器 | 存取 |
|---|---|
| Windows（本機） | `192.168.1.107`；hashcat `C:\tools\hashcat-7.1.2\`；詞表 `C:\wifi-crack\wordlists\{rockyou.txt,wifi_wordlist_combined.txt}` |
| Mac | `ssh -i C:\Users\crazydb911\.ssh\opremote_ed25519 tongbao@192.168.1.123`；sudo 密碼 `240628`；Apple Silicon；DWA-160 插在 Mac |
| Mac VM | `ssh -i ~/.ssh/vm_tongbao -p 2222 root@127.0.0.1`（VM root 密碼 `alpine123`） |

- Mac↔Win 傳檔：Mac 開 `python3 -m http.server 18642`（/tmp/vmbuild），Win curl 拉；Win→Mac 用 scp。
- runner VM 快速驗證法：`cp -a $B/irfs $B/runner` + 診斷 /init + repack + 帶 usb-host 啟動 + 等 sentinel + kill（見 PROGRESS.md）。

## 五、完成標準（definition of done）
1. Mac VM 重建後：`iw dev` 有 wlan0、dmesg 有 "Firmware detected"、10 秒 airodump 有幀。
2. 5–10 分 deauth+capture 產生可用的 `32H10F` `.hc22000` 並成功 POST 到 :8766。
3. hashcat 階段跑完並回報結果（密碼或無匹配）。
4. 無匹配 → 向使用者提出下一階方案清單（逐項確認後再執行）。