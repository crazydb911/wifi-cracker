$ErrorActionPreference = "Stop"
$game = "https://l1stw.com/"
$port = 9222
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$gameProf = "C:\Users\crazydb911\Documents\deepseek\game-profile"
$tools = "C:\Users\crazydb911\Documents\deepseek\l1stw"
$NL = [char]10

function Notify($msg) {
  Add-Type -AssemblyName System.Windows.Forms
  [System.Windows.Forms.MessageBox]::Show($msg, "掛機兩席") | Out-Null
}
function CdpUp {
  try {
    $r = Invoke-WebRequest "http://127.0.0.1:$port/json/version" -UseBasicParsing -TimeoutSec 2
    return [bool]$r.Content
  } catch { return $false }
}

# 遊戲使用獨立 game-profile，絕不關閉或觸碰使用者原本的 Chrome。
$cold = $false
if (-not (CdpUp)) {
  $cold = $true
  Start-Process $chrome -ArgumentList @(
    "--remote-debugging-port=$port",
    "--remote-allow-origins=*",
    "--user-data-dir=$gameProf",
    "--proxy-server=direct://",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-features=CalculateNativeWinOcclusion,PasswordLeakDetection,AutofillServerCommunication",
    "--no-first-run",
    "--no-default-browser-check",
    $game
  )
  $ok = $false
  foreach ($i in 1..20) { Start-Sleep -Milliseconds 750; if (CdpUp) { $ok = $true; break } }
  if (-not $ok) { Notify "遊戲專用視窗的控制埠沒起來。"; exit 1 }
}

# 啟動單實例背景重整守護（F5／遊戲自動重整時自動補注入，關窗自動退出）
Start-Process "node" -ArgumentList "cdp-keepalive.mjs" -WorkingDirectory $tools -WindowStyle Hidden

# 啟動視窗守門：視窗被最小化＝遊戲迴圈整個暫停（rAF 停、掛機白跑），20 秒內自動還原成 normal。
# 已在跑就不重複開第二個。
$guard = Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -match "window-guard\.mjs" }
if (-not $guard) { Start-Process "node" -ArgumentList "window-guard.mjs","$tools" -WorkingDirectory $tools -WindowStyle Hidden }

Push-Location $tools
$argList = @("ensure-seats.mjs")
if ($cold) { $argList += "--cold" }
$check = & node @argList 2>&1
Pop-Location

$out = "兩席狀態（" + (Get-Date -Format "HH:mm:ss") + "）" + $NL + ($check -join $NL)
$out | Out-File "$tools\seats-launch.log" -Encoding UTF8
Write-Output $out
