# WiFi破解台 交接檔

最後更新：Mac 時鐘 Nov 11 ~22:50／commit `9bbbf62b`（已推 origin/main）

## 硬性指令（違反即錯）
- 用中文回覆，不寫沒解釋的英文。
- **禁止提議買硬體**（已關掉兩次：「感覺不用特別買 只破一次而已」「不要亂推一通」）。
- **禁止要求拔插**、**禁止提議重開機**（任何一台）。
- Windows GPU 被使用者的本地模型佔用，**絕不在 Windows GPU 跑 hashcat**。
- 自己驗證過才宣稱；區分「已實作／已部署／線上可見」。
- 完工就推 GitHub。
- 還女友筆電前要 `fdesetup enable` + 取消自動登入。

## 拓撲
| 角色 | 位址 |
|---|---|
| Windows 破解端（本機） | LAN 192.168.1.107 / Tailscale 100.94.10.122，cracker :8766，hashcat `C:\tools\hashcat-7.1.2`，排程任務 `WiFiCracker` |
| Mac（女友筆電，app 以 root 跑 LaunchDaemon `com.wifi.cracker`） | 曾用 LAN 192.168.1.111、Tailscale 100.64.239.76（macbook-air-8） |
| 本地模型 omlx | 192.168.1.44:18083 |
| cliproxy 閘道 | 192.168.1.115:8318 |

Mac app = QEMU aarch64 VM（Alpine 3.24 / kernel 6.18.52-0-lts）+ D-Link DWA-160（`148f:5572` RT5572 雙頻）
管線：tcpdump 管線掃描 → hcxdumptool 攻擊 → hcxpcapngtool → POST :8766 → Windows 決策 → Mac 本地 M2 Metal hashcat 後備。

## 目前狀態（實測）
- `9bbbf62b` = HEAD = origin/main，工作區乾淨。
- **Mac 目前完全離線**：`192.168.1.111` 不在 ARP 表、tcp/22 與 tcp/8765 都連不上、Tailscale 顯示 offline。不是只有網卡——整台筆電不在網。
- Windows cracker :8766 **活著**（HTTP 有回應，`/status` 回 404 只是路徑不對）。
- 網卡 `148f:5572` 早在 Mac USB 總線消失（`ioreg` 計數 0），需要實體拔插才能恢復；使用者不在家。

### 已確立的殺卡真因
**是我們的軟體，不是硬體**：每輪 `ifconfig wlan0 down` → `iw dev wlan0 set type monitor` → `ifconfig wlan0 up`
讓 rt2800usb 永久 wedge。`ee387edd` 已預設關閉（`IF_RESET` 需 `~/wifi_cracker/ifreset.on` 才啟用）。
**左側 USB 孔（直插、無 hub）是可用孔**：撐約 7 分鐘 vs 其他孔約 2 分鐘。

## 已完成
- 隊友 `audit-sweep` 全檔只讀稽核 → 挖出 A1–A10 / B / C1–C10。
- 已修並驗證 5 條（`9bbbf62b`，`test_round.py` 14 斷言全 PASS、`test_sweepgen.py` 13 斷言全 PASS、`PYCOMPILE-OK`）：
  - **A1（地雷）** `_round` 內 `':'.join(bssid[i:i+2])` 少了 for 生成式，`i` 是 1487 行才賦值的 local → 選 AP 定向攻擊 100% `UnboundLocalError`，ssh 從未送出；`_auto_loop` 的 except 無退避 → 熱迴圈刷爆日誌。日誌計數 0 因為 `_round` 從未被呼叫過。
  - **A2** `_rca_round` 的 txpower 寫在頻道迴圈內（每輪最多 5 次 3000↔1000 抖動）→ 改 band 翻轉才寫。
  - **A3** `_scan_now` 多一個 `done` → shell rc≠0。
  - **C1** UI 錯誤日誌用了別函式的區域變數 `NL` → `NameError` 被吞，從沒寫過一個 byte。
  - **C5** `WPA*01` 的 MAC_AP 是 `f[3]` 不是 `f[2]`（同檔 1624 行自己用對了），兩處。
- 更早：`18f64b83` preheat 首輪 80s→56s、txpower 每輪最多一次；`1594d410` txpower `-95` 靜默失敗可見化（`TXPOWFAIL`）。

## 下一步（依優先序）
1. **A5**：`--bpf=/tmp/t.bpf`（`_round` 抓包行）是否 hcxdumptool 7.1.2 合法選項。隊友認為只有 `--bpfr=`／`--bpfw=`；不合法則 hcxdumptool 立即退出 → `_cap_streak` 達 3 → 每 3 輪重啟 QEMU。**不需要網卡**：`hcxdumptool --help` 不吃無線裝置，可手動開一個無卡 QEMU 驗證（QEMU 常數在 `mac_wifi_app_v2.py` L15-33，`_start_vm` L626-673），驗完立刻 kill 讓 app 收回 qcow2。指令：`chroot /newroot hcxdumptool --help 2>&1 | grep -i bpf`。
2. **C9**：`_preheat` 只在 `vm_down`／`NOWLAN` 路徑重置；另外三條 VM 重建路徑留 `True`，讓新 PHY 跳過預熱。
3. **C2/C3/C6**：掃描丟掉 tcpdump stderr 且不查 `returncode`；hcxpcapngtool 失敗被當 `vm_down`；`len(data) < 100` 把 `cat` 失敗和真空抓包混為一談。
4. **A4/A7/A8/A10、C4/C7/C8/C10**：見下方未修清單。
5. `verify_5g_attack.py` 預設 host 仍是 `192.168.1.123`，應改 `192.168.1.111`。
6. 把「左側孔」寫成 app 啟動提示。

### 未修清單（原文摘記）
- A4 `_scan_now` 每次掃描 22 次 `iw dev wlan0 set channel`，由 `_scan_loop_body` 每 ~2 秒驅動，無限期，和 sweep 搶 `_cap_lock`。
- A7 monitor 模式現在只在 `IFR` 裡設定，但三個抓包點都假設它已在（libpcap 可能每輪增刪 monitor vif 22 次）。
- A8 `_save_pcap` 的 ssh `cat` 在 `_cap_lock` **之外**，`rm -rf /tmp/*` 備援路徑可能刪掉 `/tmp/scan_*`。
- A10 `_kill_other_instances` 是死碼，`main()` 從不呼叫。
- C4 `do_GET` 的 `except Exception: pass` 不回任何 HTTP response。
- C7 potfile 讀取 `except Exception: pass` → 看起來像「沒破解」，hashcat 無限重跑。
- C8 `if text == getattr(w,'_last_text',None): return` 跳過 `w.config(fg=color)`，widget 可能留錯底色。
- C10 `raise last` 在 `eps` 空時 `raise None`；字典攻擊分支是死碼，因為 `wl` 恆為 `None`。

## 尚未取得的現場證據（不能宣稱完成）
- **5G PROBERESPONSE 注入仍未證明**：13:31 那輪 `13 BEACON / 0 PROBERESPONSE`，之後每輪都因介面死掉而無效。是「未證明」，不是「被推翻」。
- `ee387edd`／`18f64b83`／`1594d410`／`9bbbf62b` **從未對活著的網卡跑過**。
- 每輪 hash 產量 vs 基準未量測（`new=0` 每個週期）。
- 卡 wedge 後「重開 QEMU + 驅動重探」能否恢復封包流——被實體拔插擋住。

## 操作備忘
- 重啟 app：`sudo launchctl kickstart -k system/com.wifi.cracker`（`bootstrap` 會失敗：Bootstrap failed: 5）。
- 進 guest：`sudo ssh -i /Users/tongbao/.ssh/vm_tongbao -p 2222 -o StrictHostKeyChecking=no -o BatchMode=yes root@127.0.0.1`（落地 zsh）。
- 嘉客工具路徑：`hcxdumptool`／`hcxpcapngtool` 在 `/usr/local/bin/`，`iw` 在 `/usr/sbin/iw`，一律經 `chroot /newroot`（常數 `CH`）。
- **zsh 分詞**：互動遠端 zsh 要 `${=V}`；`#!/bin/sh` 腳本用一般 `$V`。`ssh '...'` 裡不能用 PowerShell 語法（`Select-Object`），改 `tail`。
- 5G 後綴：hcxdumptool 5G 是 **b**（`-c 36b`），2.4G 是 `a`。政策：36–48 主動 hcxdumptool；149+ 被動 tcpdump（DFS-CAC）。
- 5G 主動靠 initrd 內嵌簽章 `regulatory.db`+`.p7s` + preamble `iw reg set TW` → `country TW: DFS-FCC`。開機參數 `cfg80211.ieee80211_regdom=TW` 是裝飾用的。
- **絕不在 guest 動 rmmod/insmod 無線模組**（會殺掉 QEMU usb-host）。
- 驅動把 txpower 封在 23.00 dBm；PHY 衰敗時 `iw dev wlan0 set txpower fixed` 回 `-95 Not supported`。
- `~/.dsh` 沒有 live `settings.yaml`（只有 `.bak-*` 與 `.imported`）；對 `~/.dsh` 遞迴 `Get-ChildItem -Recurse` 會超過 180 秒，務必指定路徑。
- Git repo 根有數百個預存暫存檔：一律 `git add -f <特定檔>`，絕不 `git add .`，提交後確認追蹤檔數。
- Mac 是女友筆電，`/tmp` 會被重開機清空（腳本要重推）。

## 分身／模型
- 本 session 是 Team Lead `lead`；隊友 `audit-sweep`（inactive，收件匣完整，可 `send_message` 改派）、`modelprobe`（一次性，可退役）。
- **分身模型無法指定**：`spawn_teammate` 默默忽略 `model` 參數（親測：傳 `gemini-3.5-flash-lite` 落地變 `Qwen3.8-Flash-Next-Uncensored-oQ5e-mtp`）。隊友一律繼承 lead 模型。
- Nemotron 在本機所有 config 都不存在（兩個 `cordis.patch.yml` 都找過）。
- 派 code 工作的分身在 prompt 裡必須寫明**禁止動 GPU 程序**。
- 分身價值是**第二個 context window，不是速度**；快而笨的模型適合日誌分流／hash 格式清理／測試輸出摘要，不適合跨檔推理（錯的修法一樣能過 py_compile）。

## 回滾
`git revert 9bbbf62b` 或 `git checkout 1594d410 -- mac_wifi_app_v2.py`，再推 Mac 並 `kickstart`。
