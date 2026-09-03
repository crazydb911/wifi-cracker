# WiFi Cracker v10 — 計畫書

## 1. 目標

Mac 選網 → 自動抓包 → 自動分層破解（Mac）→ 難題傳 Windows 4090 → 結果回傳。
全程 Web UI 即時顯示進度、狀態、每層字典「掃完/命中」。

## 2. 架構

```
Mac (port 8765)                         Windows 4090 (port 8766)
┌──────────────────────────┐            ┌──────────────────────────┐
│  FastAPI + Socket.IO     │            │  FastAPI + Socket.IO     │
│                          │            │                          │
│  1. Scan (system_prof)   │            │  1. Receive hash+pcap    │
│  2. Capture (tshark)     │──upload───>│  2. hashcat -m 22000     │
│  3. Extract (hcxpcapng)  │            │     --status --status-timer 2
│  4. Crack local tier 1-3 │<─poll──────│  3. Progress via WS      │
│  4. Upload to Win        │            │  4. Result via API       │
│  5. Show progress (WS)   │            │  5. Thermal monitor      │
└──────────────────────────┘            └──────────────────────────┘
```

## 3. State Machine（Mac 端）

```
idle → scanning → capturing → extracting → cracking_local → uploading → win_cracking → done
                                        ↘ (all tiers exhausted) ↗
```

每個 state 對應 UI 區塊：

| State | UI 顯示 |
|-------|---------|
| `scanning` | 進度條 + 「掃射中...」 |
| `capturing` | SSID + BSSID + 倒數秒 + 已抓到 EAPOL 封包數 |
| `extracting` | 「提取 hash...」 |
| `cracking_local` | 目前 tier + 進度條 + speed + ETA + 已掃完 tier 打勾 |
| `uploading` | 「上傳至 Windows 4090...」 |
| `win_cracking` | 4090 GPU 溫度 + 進度 + speed |
| `done` | 密碼大banner 或「全部字典掃完未中」 |

## 4. 即時進度（學 AtrapaWifi）

### 4.1 技術選型：Socket.IO

- Mac + Windows 都加 `python-socketio[asyncio]`
- hashcat 加 `--status --status-timer 2`，每 2 秒輸出一次進度
- 後端 parse stdout 行 → 用 `socketio.emit("crack_progress", {...})` 推前
- 前端 `socket.on("crack_progress", handler)` 即時更新 DOM

### 4.2 hashcat 進度 parse 規則

```
Speed.#1:        12345 M-H/s   ← 速度
Progress:        12345/9999999 ← 當前/總數（dictionary attack 才有）
Time.Estimated:  2h 15m        ← 預估剩餘
Status:          Exhausted     ← 字典掃完（exit code 1）
```

### 4.3 「字典掃完」判定

- hashcat 回傳 exit code `1` = Exhausted（全部試完未中）
- 或 parse `Status: Exhausted` 行
- Mac tier N 掃完 → 自動跳 tier N+1
- 所有 tier 掃完 → 自動上傳 Windows

## 5. Mac → Windows 同步

### 5.1 上傳內容

```json
POST http://<win>:8766/api/crack
{
  "hash": "WPA*02*...",
  "ssid": "TargetNetwork",
  "bssid": "aa:bb:cc:dd:ee:ff",
  "pcap_base64": "...",    // 小檔才傳
  "tiers_completed": ["rockyou", "wifi_combined"],  // Mac 已掃完的
  "next_tier": "best66"    // 建議 Windows 從哪層開始
}
```

### 5.2 Windows 回傳

Windows 破完後 Mac poll `/api/result?task_id=xxx`：
```json
{
  "status": "cracked" | "exhausted" | "error",
  "password": "abc123",       // cracked 時有
  "tier": "best66",
  "elapsed": 342,
  "gpu_peak_temp": 81
}
```

## 6. 分層字典策略（保留 v9，加狀態）

| Tier | 字典 | Mac 跑 | Windows 跑 |
|------|------|--------|-----------|
| 1 | rockyou (490) | ✓ | - |
| 2 | wifi_combined (175K) | ✓ | - |
| 3 | best66 (11M) | - | ✓ (GPU) |
| 4 | ?d×8 brute (11M) | - | ✓ (GPU) |
| 5 | ?d×9 brute (1B) | - | ✓ (GPU) |

每層完成時 STATE 加 `"tier_results": {"rockyou": "exhausted", ...}`。

## 7. 前端 UI 改版

保留 v9 深色主題，加：
- **進度條**：每層字典一條，掃完變綠 ✓
- **即時 speed/ETA**：Socket.IO 推送
- **Windows 4090 卡片**：GPU 溫度、util、speed 即時更新
- **Tier 結果列表**：每層狀態（跑中/掃完/命中）
- **最終 banner**：密碼 or 「全部掃完」

## 8. 技術棧

| 端 | 框架 | 即時通訊 | 破解引擎 |
|----|------|---------|---------|
| Mac | FastAPI | python-socketio | hashcat (Apple Silicon) + hcxpcapngtool + tshark |
| Windows | FastAPI | python-socketio | hashcat (RTX 4090) |

## 9. 檔案結構

```
mac_wifi_cracker_v10.py    # Mac 端（單檔，port 8765）
windows_cracker_v10.py     # Windows 端（單檔，port 8766）
PLAN_v10.md                # 本計畫書
README.md                  # 更新架構說明
```

## 10. 實施順序

1. **Mac 端**：加 Socket.IO、hashcat `--status` parse、tier 狀態機、即時進度
2. **Windows 端**：加 Socket.IO、`--status` parse、結果回傳 API
3. **前端**：進度條、tier 列表、WS 接收、Windows 卡片
4. **聯調**：Mac 掃完 tier 1-2 → 自動上傳 → Windows 跑 tier 3-5 → 結果回傳

## 11. 參考來源

- [WiFiCrack](https://github.com/phenotypic/WiFiCrack) — macOS 抓包流程
- [AtrapaWifi](https://github.com/FomoDonkey/AtrapaWifi) — SocketIO 即時進度、hashcat parse 模式
- [hcxdumptool 生態](https://github.com/andrewdesch/hcxdumptool) — hcxpcapngtool 用法
