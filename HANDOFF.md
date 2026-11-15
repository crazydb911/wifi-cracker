# WiFi破解台 交接檔

最後更新：Mac 時鐘 Nov 15 17:56／commit `197715f1`（已推 origin/main）

> **Mac LAN IP 已從 `192.168.1.111` 改成 `192.168.1.117`（DHCP 續約）。** 連不上時先重查 ARP，別誤判成離線。
> SSH：`ssh -i C:/Users/crazydb911/.ssh/opremote_ed25519 tongbao@192.168.1.117`（落地 zsh）。跨三層引號用 base64 送腳本：`"echo <b64> | base64 -d | zsh"`。

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
| Mac（女友筆電 M2，`tongbaodeMacBook-Air`，app 以 root 跑 LaunchDaemon `com.wifi.cracker`） | **LAN 192.168.1.117**（原 .111）、Tailscale 100.64.239.76 `m2-tongbao`（常 offline） |
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
1. ~~**A5**~~ **已結案，隊友判斷錯誤（Nov 15 實測，見下方「A5 結案」）。** 下一件事改成：**C9**（`_preheat` 重置路徑不全）與 **C2**（掃描吞掉 tcpdump stderr、不查 returncode）。
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

## A5 結案：hcxdumptool 旗標全數驗證（Nov 15，**不需要網卡**）

用**無卡 QEMU**（7 秒上線）在 guest 內逐旗標比對。**方法關鍵**：hcxdumptool 先查介面、後查選項，所以 `-i wlan0`（無卡時不存在）會讓所有測試都回 `failed to get interface index`，看不出差別——**必須拿存在的 `eth0` 當對照組**才會抵達選項驗證。

| 旗標 | 結果 |
|---|---|
| `-c 6a` / `-c 36b` | accepted |
| `-w` / `-t` / `--rds=2` | accepted |
| `--rcascan=active` | accepted |
| **`--bpf=/tmp/t.bpf`** | **accepted（app 用法正確）** |
| `--m2max=16` | accepted |
| **`--bpfr=`（隊友建議改的）** | **REJECTED — 7.1.2 沒這個選項** |
| `hcxpcapngtool --all -o` | accepted |
| 對照組 `--zzzz=1` | `unrecognized option`（證明測試有效） |

BPF 管線端到端也測了：`tcpdump -y IEEE802_11 -dd "wlan addr1 … or type mgt subtype probereq"` → 814 bytes 正確位元組碼（`0x4ca0` = coverage log 那台 4ca0e3 的 OUI）→ hcxdumptool 收得下去。

**教訓**：隊友的 A5 若照改會把能動的選項弄壞。分身的發現一律要自己設計對照組重測。

### 無卡 QEMU 探測法（可重用，已驗證）
app 在 `no_card_on_bus_skip_qemu` 狀態下不會起 QEMU，所以 qcow2 沒人用，可手動開一台探測機。**不要帶 `usb-host` 裝置**（無卡時會拖死啟動），這樣在裡面 insmod 也不傷 usb-host。
```
sudo nohup /opt/homebrew/bin/qemu-system-aarch64 -machine virt -cpu cortex-a72 -m 1024 -smp 2 \
  -drive file=/Users/tongbao/vmbuild/alpine-root.qcow2,format=qcow2 \
  -kernel /Users/tongbao/vmbuild/alpine-boot/boot/vmlinuz-lts \
  -initrd /Users/tongbao/vmbuild/vmbuild/runner-initrd \
  -append "console=ttyAMA0 cfg80211.ieee80211_regdom=TW" \
  -chardev file,id=s0,path=/tmp/probe_serial.log,append=on -serial chardev:s0 \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:2222-10.0.2.15:22 \
  -device virtio-net-pci,netdev=n0 -device qemu-xhci,id=xhci \
  -display none -monitor unix:/tmp/probe_monitor.sock,server,nowait \
  > /tmp/probe_qemu.err 2>&1 &
```
進 guest：`ssh -i /Users/tongbao/.ssh/vm_tongbao -p 2222 -o StrictHostKeyChecking=no root@127.0.0.1`（落地 initramfs shell，`/newroot` 已掛，所以一律 `chroot /newroot`）。
用完 `sudo pkill -f probe_monitor.sock`；驗完 app 照常 `no_card_on_bus_skip_qemu`，無副作用。
**限制**：guest 無 `mac80211_hwsim`（`find /lib/modules -name '*hwsim*'` 空），所以**無法**在無卡情況下建 monitor 介面 → 完整抓包管線實測仍需實體卡。

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


## 2026-11-15 傍晚現場實測（使用者拔插兩次，左孔→另一孔）

### 已證明（工具輸出為證）
- **每頻道立即轉換上傳補丁有效**：18:36:43 預熱 → 18:37:17 `cycle ch=3 raw=0 new=0`，34 秒跑完，**沒有 vm_down**。這是第一次跑完整輪。
- **卡壽命實測 45 秒**（18:24:26 wlan0 出現 → 18:25:11 消失）。
- **`raw=0`**：hcxpcapngtool 一顆 hash 都沒吐。不是重複問題（hash 池 1892 行未成長）。
- **RX 沒有壞**：介面停在 channel 36(5G) 時 tcpdump 0 packets；`iw dev wlan0 set channel 1` 後 12 秒抓到 **3 packets**。所以「零封包」是**頻道假象**，不是硬體死。
- **真正的瓶頸是產量**：hcxpcapngtool 明說 `This dump file does not contain enough EAPOL M1 frames` —— 收到 beacon/probe，**收不到握手**。
- `iw dev wlan0 info`：`type monitor` 正常、`txpower 23.00 dBm`（驅動封頂）。A7（monitor 沒人設）此刻未咬。
- `iw dev wlan0 scan` 回 **0 BSS**（monitor 模式下韌體掃描不給結果，不能當成「掃不到」）。
- survey：2412 MHz active time 1309 ms → 無線有感应到能量。
- hcxdumptool 自報 `3 ERROR(s) during runtime: mostly caused by a broken driver`。
- `TXPOWFAIL` 觸發兩次 → PHY 拒絕降功率。

### 環境變更（重要）
- **Tailscale 已啟動**：Mac = `100.64.239.76` (`macbook-air-8`)，Windows = `100.94.10.122` 在線。**使用者出門後仍可遠端讀 Mac**。LAN IP 仍 192.168.1.117。
- 睡眠設定：AC 與電池皆 `sleep 0`、`displaysleep 0`、`disksleep 0`，另有常驻 caffeinate（pid 421）→ **不會自動睡眠**。但**關蓋仍會睡**。
- **電池警訊**：78%、`Charging: No`、适配器 `Wattage 15W`（M2 Air 需 30W+）。負載下可能邊充邊掉。Cycle 31 / Condition Normal / Max Capacity 100% → 電池本體健康，是**供電不足**。
- 監視器換成不限量迴圈 `/tmp/field_watch.sh`（pid 30222）→ `/tmp/field_watch.log`。

### 未完成 / 下一步
- 零 hash 的根因尚未收斂：要區分「hcxdumptool 主動攻擊沒打出流量」與「45 秒內本來就抓不到握手」。做法：在 busy 2.4G 頻道跑 `aireplay` 式 deauth 或拉長單頻道 dwell，同時看 EAPOL 計數。
- 5G 主動注入仍未證明（BEACON 有、PROBERESPONSE 0）。
- 待修清單 A4/A7/A8/A10/C2/C4/C6/C7/C8/C9/C10 未動。
