# Mac 狀態備註 (2026-09-03)

## 目前狀態
Mac (192.168.1.118) SSH 連不上，ICMP ping 也沒回應。

## 可能原因
- Mac 筆記型電腦合蓋睡覺了
- WiFi 重啟後沒自動重連
- 網路線鬆了（如果是桌上型）

## 你醒來後要做的事
1. **打開 Mac / 按鍵盤** 喚醒
2. 確認 WiFi 或網路有連上
3. 打開終端機執行:
   ```
   cd ~/wifi_cracker
   python3 mac_wifi_cracker_v10.py &
   ```
4. 打開瀏覽器到 http://192.168.1.118:8765 看破解進度
5. 如果 32H9F (或 32H10F) 不在 WiFi 掃描列表中，代表 Mac 不在訊號範圍內

## Windows 4090 狀態
✅ 已重新啟動 (port 8766 LISTENING, PID 7280)

## GitHub
✅ 已更新到 v10 (commit 3dadaa4)
https://github.com/crazydb911/wifi-cracker

## 目標網路
- 你說的是 "32H10F"，但 Mac 已存的 WiFi 是 "32H9F" 和 "32H9F_5G"
- 很可能是一個字的差異 (9 vs 10)
- 兩次掃描都沒看到這個網路，可能 Mac 離路由器太遠
