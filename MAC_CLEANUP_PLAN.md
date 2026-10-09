# Mac 還女友前清場計畫（下週執行）

原則：**保留女友的 GPT 控制鏈（control plane）**，其他我裝的全部清掉。
時間未到，先盤點；執行時照單勾銷。

## ✅ 保留（GPT 控制鏈，實測都在跑）
| 項目 | 位置 | 說明 |
|---|---|---|
| MacControlAgent | `~/Applications/MacControlAgent.app` | 控制鏈主體（LaunchAgent 常驻） |
| 啟動代理 | `~/Library/LaunchAgents/local.aicontrol.MacControlAgent.plist` | KeepAlive |
| 資料 | `~/.aicontrol/` | 控制鏈設定/對話 |
| Desktop Commander | `~/.desktop-commander-agent`、`~/.desktop-commander-device` | GPT 控制 Mac 的 MCP 代理 |
| 啟動代理 | `~/Library/LaunchAgents/com.crazydb911.desktopcommander.remote.plist` | 用 homebrew node 跑 |
| 疑似控制鏈 | `~/.m2control`、`~/.modloop`、`~/.claude-server-commander*` | ⚠️ 執行前跟女友確認 |
| Homebrew + node | `/opt/homebrew` | desktop-commander 相依，**不能砍** |

## ❌ 清除（WiFi 破解相關，共約 2.7GB）
- [ ] `~/vmbuild/`（2.7G：Alpine rootfs、kernel、initrd）
- [ ] `~/wifi_cracker/`（2.9M：mac_wifi_app_v2.py 等）
- [ ] `~/Desktop/MacCapture.app`
- [ ] `~/MacCapture/`（0B 殘留）
- [ ] `~/.ssh/vm_tongbao`、`vm_tongbao.pub`（VM 金鑰）
- [ ] `/tmp/mac_wifi_*`、`/tmp/vm_app_*`、`/tmp/_win.scpt`
- [ ] `brew uninstall qemu`（含 pixman 等相依）
- [ ] `pip3 uninstall py-spy`（我裝的除錯工具）

## ❌ 恢復系統設定（我改過的）
- [ ] 關閉螢幕共享：`sudo launchctl bootout system/com.apple.screensharing`
- [ ] 重開 Spotlight：`sudo mdutil -a -i on`
- [ ] 恢復桌面設定：`defaults delete com.apple.wallpaper BugInducedReliability`
- [ ] 輔助使用/螢幕錄影授權：系統設定 → 私隱與保安 → 移除 Terminal/osascript 的授權
- [ ] 遠端登入（SSH）：女友不需要就關掉（系統設定 → 一般 → 共享 → 遠端登入）
- [ ] known_hosts 清理（`~/.ssh/known_hosts` 內 127.0.0.1:2222 等行）

## 執行順序（下週）
1. 先確認控制鏈健康：`launchctl print gui/501/local.aicontrol.MacControlAgent`、`...desktopcommander.remote` 都在跑
2. 關 App + QEMU（`pkill -f mac_wifi_app_v2; pkill -f qemu-system-aarch64`）
3. 照上面清單刪檔、卸載、恢復設定
4. 重開機 → 確認控制鏈自動起來、沒有殘留 QEMU/App
5. 交機

## Windows 端（不用動）
- 破解都在 Windows：`windows_cracker_app.py`（:8766）+ hashcat 留著
- GitHub `wifi-cracker` repo 留檔，Mac 清掉不影響
