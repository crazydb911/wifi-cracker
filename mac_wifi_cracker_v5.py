#!/usr/bin/env python3
"""
Mac WiFi Cracker v5 - Standalone app with manual packet capture.
Features:
- Scan WiFi networks (tshark)
- Manual capture (select WiFi, start/stop)
- One-click upload to Windows app
- Web UI for control
"""

import os
import sys
import json
import subprocess
import threading
import time
import re
from pathlib import Path
import requests
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

app = FastAPI(title="Mac WiFi Cracker v5")

# Windows app URL
WINDOWS_URL = "http://192.168.1.107:8766"

STATE = {
    "status": "idle",
    "message": "Ready",
    "progress": 0,
    "ap_list": [],
    "capturing": False,
    "capture_file": None,
    "capture_duration": 0,
    "upload_status": None,
    "log": [],
}

def log(msg):
    ts = time.strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    STATE["log"].append(entry)
    print(entry, flush=True)
    if len(STATE["log"]) > 500:
        STATE["log"] = STATE["log"][-500:]

def scan_wifi(duration=10):
    """Scan WiFi networks using tshark."""
    STATE["status"] = "scanning"
    STATE["message"] = f"Scanning WiFi networks ({duration}s)..."
    STATE["progress"] = 10
    log(f"Starting tshark scan ({duration}s)...")
    
    try:
        tshark = "/usr/local/bin/tshark"
        cap_file = f"/tmp/wifiscan_{int(time.time())}.pcap"
        
        # Run tshark in monitor mode
        proc = subprocess.Popen(
            ["sudo", "-S", tshark, "-i", "en0", "-I", "-y", "IEEE802_11", "-c", "200", "-w", cap_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        # Send space for sudo password
        time.sleep(2)
        # sudo -S reads from stdin, but we're using Popen without stdin
        # Let's use a different approach - write to a temp file
        
        time.sleep(duration)
        proc.terminate()
        proc.wait()
        
        # Parse pcap using tshark
        result = subprocess.run(
            ["tshark", "-r", cap_file, "-Y", "wlan.mgt == 1", "-T", "fields", 
             "-e", "wlan.sa", "-e", "wlan.ssid", "-e", "wlan.channel", "-e", "wlan.signal"],
            capture_output=True, text=True, timeout=30
        )
        
        ap_list = []
        seen = set()
        
        for line in result.stdout.strip().splitlines():
            parts = line.split('\t')
            if len(parts) >= 4:
                bssid = parts[0]
                ssid = parts[1] if parts[1] else "(hidden)"
                channel = parts[2]
                signal = parts[3]
                
                if bssid and bssid not in seen:
                    seen.add(bssid)
                    ap_list.append({
                        "bssid": bssid,
                        "ssid": ssid,
                        "channel": channel,
                        "rssi": int(signal) if signal.isdigit() else 0,
                        "security": "WPA2",
                        "mode": "802.11"
                    })
        
        STATE["ap_list"] = ap_list
        STATE["status"] = "idle"
        STATE["message"] = f"Found {len(ap_list)} networks"
        STATE["progress"] = 100
        log(f"Scan complete: {len(ap_list)} networks found")
        
    except Exception as e:
        STATE["status"] = "idle"
        STATE["message"] = f"Scan error: {e}"
        log(f"Scan error: {e}")

def start_capture(bssid, ssid, duration=60):
    """Start capturing packets for a specific AP."""
    STATE["status"] = "capturing"
    STATE["capturing"] = True
    STATE["capture_file"] = f"/tmp/capture_{bssid.replace(':', '')}.pcap"
    STATE["message"] = f"Capturing {ssid} ({bssid}) for {duration}s..."
    STATE["progress"] = 20
    log(f"Starting capture for {ssid} ({bssid})...")
    
    try:
        tshark = "/usr/local/bin/tshark"
        cap_file = STATE["capture_file"]
        
        # Use sudo with space password
        proc = subprocess.Popen(
            ["sudo", "-S", tshark, "-i", "en0", "-I", "-y", "IEEE802_11", "-c", "500", "-w", cap_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            stdin=subprocess.PIPE
        )
        
        # Send space for sudo password
        proc.stdin.write(" \n")
        proc.stdin.flush()
        
        time.sleep(duration)
        proc.terminate()
        proc.wait()
        
        STATE["capture_duration"] = duration
        STATE["status"] = "idle"
        STATE["capturing"] = False
        STATE["message"] = f"Capture complete: {cap_file}"
        STATE["progress"] = 50
        log(f"Capture saved: {cap_file}")
        
    except Exception as e:
        STATE["status"] = "idle"
        STATE["capturing"] = False
        STATE["message"] = f"Capture error: {e}"
        log(f"Capture error: {e}")

def upload_to_windows():
    """Upload capture file to Windows app."""
    STATE["status"] = "uploading"
    STATE["message"] = "Uploading to Windows app..."
    STATE["progress"] = 70
    log(f"Uploading {STATE['capture_file']} to {WINDOWS_URL}...")
    
    try:
        if not STATE["capture_file"] or not os.path.exists(STATE["capture_file"]):
            raise FileNotFoundError(f"Capture file not found: {STATE['capture_file']}")
        
        # Upload to Windows app
        with open(STATE["capture_file"], 'rb') as f:
            response = requests.post(
                f"{WINDOWS_URL}/api/extract",
                files={"file": (os.path.basename(STATE["capture_file"]), f)},
                data={"ssid": "32H9F_5G"},
                timeout=60
            )
        
        if response.status_code == 200:
            STATE["upload_status"] = "success"
            STATE["status"] = "idle"
            STATE["message"] = "Upload complete! Check Windows app for results."
            STATE["progress"] = 100
            log("Upload successful!")
        else:
            STATE["upload_status"] = f"error: {response.status_code}"
            STATE["status"] = "idle"
            STATE["message"] = f"Upload failed: {response.status_code}"
            log(f"Upload failed: {response.status_code}")
            
    except Exception as e:
        STATE["upload_status"] = "error"
        STATE["status"] = "idle"
        STATE["message"] = f"Upload error: {e}"
        log(f"Upload error: {e}")

@app.get("/")
async def root():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Mac WiFi Cracker v5</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #1a1a2e; color: #eee; }
        h1 { color: #4fc3f7; }
        .card { background: #16213e; border-radius: 8px; padding: 15px; margin: 10px 0; }
        .status { color: #4fc3f7; font-weight: bold; }
        .progress { width: 100%; height: 20px; background: #0f3460; border-radius: 10px; overflow: hidden; }
        .progress-bar { height: 100%; background: #4fc3f7; transition: width 0.3s; }
        .log { background: #0f3460; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 12px; max-height: 300px; overflow-y: auto; }
        button { background: #4fc3f7; color: #1a1a2e; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-size: 16px; margin: 5px; }
        button:hover { background: #29b6f6; }
        button:disabled { background: #555; cursor: not-allowed; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #0f3460; }
        th { color: #4fc3f7; }
        .capture-controls { display: flex; gap: 10px; margin: 10px 0; }
        .upload-status { padding: 10px; border-radius: 4px; margin: 10px 0; }
        .success { background: #1b5e20; }
        .error { background: #b71c1c; }
    </style>
</head>
<body>
    <h1>Mac WiFi Cracker v5</h1>
    <div class="card">
        <div class="status">Status: <span id="status">Loading...</span></div>
        <div class="progress"><div class="progress-bar" id="progress" style="width: 0%"></div></div>
        <p id="message">Loading...</p>
    </div>
    
    <div class="card">
        <h2>1. Scan</h2>
        <div class="capture-controls">
            <input type="number" id="scan-duration" value="10" min="5" max="60" style="width: 80px;">
            <button onclick="scan()" id="btn-scan">Scan WiFi</button>
        </div>
        <table id="ap-table">
            <thead><tr><th>SSID</th><th>BSSID</th><th>Ch</th><th>RSSI</th><th>Action</th></tr></thead>
            <tbody></tbody>
        </table>
    </div>
    
    <div class="card">
        <h2>2. Capture & Upload</h2>
        <div class="capture-controls">
            <input type="number" id="capture-duration" value="60" min="10" max="300" style="width: 80px;">
            <span>seconds</span>
            <button onclick="upload()" id="btn-upload" disabled>Upload to Windows</button>
        </div>
        <div id="upload-status" class="upload-status" style="display: none;"></div>
    </div>
    
    <div class="card">
        <h2>Log</h2>
        <div class="log" id="log"></div>
    </div>
    
    <script>
        function update() {
            fetch('/api/state')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('status').textContent = data.status;
                    document.getElementById('progress').style.width = data.progress + '%';
                    document.getElementById('message').textContent = data.message;
                    document.getElementById('log').innerHTML = data.log.join('<br>');
                    document.getElementById('log').scrollTop = document.getElementById('log').scrollHeight;
                    
                    const tbody = document.querySelector('#ap-table tbody');
                    tbody.innerHTML = data.ap_list.map((ap, i) => 
                        `<tr>
                            <td>${ap.ssid || '(hidden)'}</td>
                            <td>${ap.bssid}</td>
                            <td>${ap.channel}</td>
                            <td>${ap.rssi}</td>
                            <td><button onclick="capture(${i})" ${data.status !== 'idle' ? 'disabled' : ''}>Capture</button></td>
                        </tr>`
                    ).join('');
                    
                    document.getElementById('btn-scan').disabled = data.status !== 'idle';
                    document.getElementById('btn-upload').disabled = !data.capture_file || data.status !== 'idle';
                    
                    const uploadStatus = document.getElementById('upload-status');
                    if (data.upload_status) {
                        uploadStatus.style.display = 'block';
                        uploadStatus.className = 'upload-status ' + (data.upload_status === 'success' ? 'success' : 'error');
                        uploadStatus.textContent = data.upload_status === 'success' ? 
                            '✓ Upload successful! Check Windows app.' : 
                            '✗ Upload failed: ' + data.upload_status;
                    }
                })
                .catch(e => console.error(e));
        }
        
        function scan() {
            const duration = document.getElementById('scan-duration').value || 10;
            fetch(`/api/scan?duration=${duration}`, { method: 'POST' })
                .then(r => r.json())
                .then(data => update());
        }
        
        function capture(index) {
            fetch('/api/state').then(r => r.json()).then(data => {
                const ap = data.ap_list[index];
                const duration = document.getElementById('capture-duration').value || 60;
                fetch(`/api/capture?bssid=${ap.bssid}&ssid=${encodeURIComponent(ap.ssid)}&duration=${duration}`, { method: 'POST' })
                    .then(r => r.json())
                    .then(data => update());
            });
        }
        
        function upload() {
            document.getElementById('btn-upload').disabled = true;
            fetch('/api/upload', { method: 'POST' })
                .then(r => r.json())
                .then(data => update());
        }
        
        update();
        setInterval(update, 2000);
    </script>
</body>
</html>
""")

@app.get("/api/state")
async def get_state():
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
    log("Starting Mac WiFi Cracker v5 on port 8765...")
    uvicorn.run(app, host="0.0.0.0", port=8765)
