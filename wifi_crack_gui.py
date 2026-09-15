# -*- coding: utf-8 -*-
"""
WiFi Crack GUI — WPA2 PMKID (hashcat -m 22000) 多階段字典破解 + 暫停/繼續
=========================================================================
啟動: 雙擊 wifi_crack_gui.bat (pythonw, 無終端視窗)

暫停機制 (v7.1.2 無 --restore-timer, 監控線程約每小時自動寫 restore 檔):
  暫停 = TerminateProcess (殺 hashcat)  → 最多丟失約 1 小時進度
  繼續 = --restore --restore-file-path restore_stage<N>.bin
  重開 app → 自動從 restore 檔繼續
"""
import os
import re
import sys
import json
import time
import glob
import gzip
import queue
import threading
import subprocess
import traceback

# ---------- HiDPI ----------
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

# ---------- 常數 (與 CLI 版完全一致) ----------
HC_DIR  = r"C:\wifi-crack\hashcat-7.1.2"
HC      = HC_DIR + r"\hashcat.exe"
RULES   = HC_DIR + r"\rules"
R_B66   = RULES + r"\best66.rule"
R_30K   = RULES + r"\rockyou-30000.rule"
WL      = r"C:\wifi-crack\wordlists"
WIFI_WL = WL + r"\wifi_wordlist_combined.txt"   # base 176K
ROCK    = WL + r"\rockyou.txt"                  # base 14M
ROCK_GZ = WL + r"\rockyou.txt.gz"
CRACKED = WL + r"\cracked.txt.gz"               # WPA 專用 805K (wpa-sec.stanev.org, 大神推薦)
INBOX   = r"C:\wifi-crack\crack_inbox"
RESULT  = r"C:\wifi-crack\crack_results"
STATE   = RESULT + r"\state.json"
POT     = RESULT + r"\hashcat.potfile"
GUI_LOG = RESULT + r"\gui.log"
LOCK    = RESULT + r"\gui.lock"
MODE    = 22000

STAGE_DEFS = [
    (1, "SSID 衍生詞庫 (32H10F 組合)", None,               None),
    (2, "wifi_wordlist base (176K)",   WIFI_WL,            None),
    (3, "cracked.txt WPA 專用 (805K)", CRACKED,            None),  # 大神推薦 wpa-sec.stanev.org
    (4, "rockyou base (14M)",          ROCK,               None),
    (5, "rockyou + best66.rule (~5.3B)", ROCK,             R_B66),
    (6, "rockyou + rockyou-30000.rule (~430B)", ROCK,      R_30K),
]

# ---------- 狀態檔 ----------
def default_state(ssid=""):
    return {
        "ssid": ssid, "gear": 80, "cracked": False, "password": None,
        "stages": {str(i): {"status": "pending", "progress": None}
                   for i, _, _, _ in STAGE_DEFS},
    }

def load_state():
    try:
        with open(STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def save_state(st):
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE)

# ---------- 工具 ----------
def find_hashfile():
    hits = sorted(glob.glob(r"C:\wifi-crack\captures\*.22000"))
    if not hits:
        hits = sorted(glob.glob(r"C:\wifi-crack\captures\*.hccapx"))
    return hits[0] if hits else None

def extract_ssid(hf):
    if hf and hf.lower().endswith(".22000"):
        with open(hf, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.strip().startswith("$PMKID$"):
                    return line.strip().split("$", 4)[3]
    return ""

def ensure_rockyou():
    if os.path.exists(ROCK) and os.path.getsize(ROCK) > 100_000_000:
        return
    if os.path.exists(ROCK_GZ):
        with gzip.open(ROCK_GZ, "rb") as fin, open(ROCK, "wb") as fout:
            while True:
                b = fin.read(1 << 20)
                if not b:
                    break
                fout.write(b)

def gen_ssid_wl(ssid):
    out = RESULT + r"\ssid_wl_%s.txt" % ssid
    if os.path.exists(out):
        return out
    import itertools
    base = set()
    for n in range(2, 7):
        for perm in itertools.permutations(ssid, n):
            base.add("".join(perm))
    for s in list(base):
        base.add(s.lower()); base.add(s.upper())
        base.add(s + "1"); base.add(s + "123"); base.add(s + "1234")
        base.add(s + "2024"); base.add(s + "2025"); base.add(s + "888")
        base.add("a" + s); base.add(s + "a")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(sorted(base)) + "\n")
    return out

def stage_wordlist(sid, ssid):
    if sid == 1:
        p = RESULT + r"\ssid_wl_%s.txt" % ssid
        return p if os.path.exists(p) else None
    return dict((i, w) for i, _, w, _ in STAGE_DEFS)[sid]

def stage_rule(sid):
    return dict((i, r) for i, _, _, r in STAGE_DEFS).get(sid)

def check_crack(hf):
    try:
        r = subprocess.run([HC, "--potfile-path", POT, "--session", "gui_show",
                            "-m", str(MODE), "--show", hf],
                           cwd=HC_DIR, capture_output=True, timeout=120,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        for line in r.stdout.decode("utf-8", "replace").splitlines():
            if ":" in line and not line.strip().startswith("#"):
                a, b = line.split(":", 1)
                if a.strip().startswith("$"):
                    return b.strip()
    except Exception:
        pass
    return None

def apply_gear(pct=None):
    # 功率限制已拿掉 (GPU power 由外部自行控制) — no-op, 不再呼叫 nvidia-smi -pl
    return True

def running_processes():
    """回傳執行中的 hashcat / python 行程 (GPU 搶佔檢查)."""
    out = []
    try:
        r = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                           capture_output=True, timeout=10)
        for line in r.stdout.decode("utf-8", "replace").splitlines():
            line = line.strip().strip('"')
            low = line.lower()
            if "hashcat" in low or "python" in low:
                out.append(line)
    except Exception:
        pass
    return out

def is_pid_alive(pid):
    try:
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == STILL_ACTIVE
    except Exception:
        return False

# ---------- 狀態行解析 ----------
RE_SPEED   = re.compile(r"Speed\.\S*?:\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*([kMGT]?H/s)")
RE_PROG    = re.compile(r"Progress\.[^\d]*(\d+)/(\d+)")
RE_RESTORE = re.compile(r"Restore\.Point\.[^\d]*(\d+)/(\d+)")
RE_ELAPSED = re.compile(r"Time\.Started\S*?:.*\(([^)]+)\)")
RE_ETA     = re.compile(r"Time\.Estimated\S*?:.*\(([^)]+)\)")
RE_STATUS  = re.compile(r"Status\.[^\w]*(\w+)")
RE_REJECT  = re.compile(r"Rejected\.[^\d]*(\d+)/(\d+)")
RE_HWMON   = re.compile(r"Hardware\.Mon\.\S*?:.*?Temp:\s*(\d+)c.*?Fan:\s*(\d+)%")
RE_DUR     = re.compile(r"(\d+)\s*(days?|hours?|mins?|secs?)")

def dur_to_sec(s):
    """'2 days, 6 hours' / '5 mins' / '45 secs' → 秒."""
    tot = 0
    for num, unit in RE_DUR.findall(s):
        n = int(num)
        if unit.startswith("day"):
            tot += n * 86400
        elif unit.startswith("hour"):
            tot += n * 3600
        elif unit.startswith("min"):
            tot += n * 60
        else:
            tot += n
    return tot

def fmt_dur(sec):
    sec = int(sec)
    d, rem = divmod(sec, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if d:
        return "%d days %02dh %02dm" % (d, h, m)
    if h:
        return "%dh %02dm" % (h, m)
    if m:
        return "%dm %02ds" % (m, s)
    return "%ds" % s

# =====================================================================
#  Worker (執行緒)
# =====================================================================
class Worker(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.pause_evt  = threading.Event()   # UI 按「暫停」
        self.resume_evt = threading.Event()   # UI 按「繼續」
        self.stop_evt   = threading.Event()   # 視窗關閉
        self.proc = None
        self.current_sid = None
        self.status = {}                      # 最新解析出的狀態
        self.log_q = queue.Queue()
        self.cracked_pw = None
        self.fatal = None

    # ---- 日誌 (只入佇列; 主執行緒 poll 時才碰 widget) ----
    def log(self, text):
        self.log_q.put(text)

    def is_running_hashcat(self):
        return self.proc is not None and self.proc.poll() is None

    # ---- 主迴圈 ----
    def run(self):
        try:
            st = load_state()
            if st is None:
                st = default_state(self.app.ssid)
            while not self.stop_evt.is_set():
                sid, resume = self.pick_stage(st)
                if sid is None:
                    self.log("—— 全部階段完成，未找到密碼 ——")
                    break
                paused = self.run_stage(st, sid, resume)
                if paused and not self.stop_evt.is_set():
                    # 等待「繼續」
                    while not self.stop_evt.is_set() and not self.resume_evt.is_set():
                        time.sleep(0.2)
                    self.resume_evt.clear()
                    if self.stop_evt.is_set():
                        break
            self.log_q.put(("__done__", None))
        except Exception:
            self.fatal = "".join(traceback.format_exception(*sys.exc_info()))
            self.log_q.put(("__fatal__", self.fatal))

    def pick_stage(self, st):
        stages = st.get("stages", {})
        for sid, _, _, _ in STAGE_DEFS:
            k = str(sid)
            info = stages.get(k, {})
            status = info.get("status", "pending")
            if status in ("running", "paused"):
                # 未乾淨結束 / 已暫停 → 有 restore 檔就接續
                resume = os.path.exists(RESULT + r"\restore_stage%d.bin" % sid)
                return sid, resume
        for sid, _, _, _ in STAGE_DEFS:
            if stages.get(str(sid), {}).get("status", "pending") == "pending":
                resume = os.path.exists(RESULT + r"\restore_stage%d.bin" % sid)
                return sid, resume
        return None, False

    # ---- 執行單階段 ----
    def run_stage(self, st, sid, resume):
        label = dict((i, l) for i, l, _, _ in STAGE_DEFS)[sid]
        wl = stage_wordlist(sid, self.app.ssid)
        if wl is None or not os.path.exists(wl):
            self.log("階段 %d 詞庫不存在: %s" % (sid, wl))
            return False
        rule = stage_rule(sid)
        restore = RESULT + r"\restore_stage%d.bin" % sid
        cmd = [HC, "-m", str(MODE), "-a", "0", "-w", "3",
               "--backend-devices-keepfree=98",
               "--potfile-path", POT,
               "--session", "stage%d" % sid,
               "--restore-file-path", restore,
               "--status", "--status-timer", "2"]
        if resume and os.path.exists(restore):
            cmd.append("--restore")
            self.log("▶ 階段 %d (%s) — 從 restore 檔接續" % (sid, label))
        else:
            self.log("▶ 階段 %d (%s) — 開始" % (sid, label))
        if rule:
            cmd += ["-r", rule]
        cmd += [self.app.hf, wl]

        stages = st.setdefault("stages", {})
        stages[str(sid)] = {"status": "running", "progress": stages.get(str(sid), {}).get("progress")}
        save_state(st)
        self.current_sid = sid
        self.status = {}

        try:
            proc = subprocess.Popen(
                cmd, cwd=HC_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            self.log("hashcat 啟動失敗: %s" % e)
            stages[str(sid)]["status"] = "paused"
            save_state(st)
            return True
        self.proc = proc

        try:
            for raw in proc.stdout:
                line = raw.decode("utf-8", "replace").rstrip()
                if not line.strip():
                    continue
                self.log(line)
                self.parse_status(line)
                if self.pause_evt.is_set():
                    break
        except Exception:
            pass
        finally:
            paused = self.pause_evt.is_set()
            if paused:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc.stdout.close()
            except Exception:
                pass
        rc = proc.wait()
        self.proc = None

        if paused:
            stages[str(sid)]["status"] = "paused"
            stages[str(sid)]["progress"] = self.status.get("progress")
            save_state(st)
            self.log("⏸ 階段 %d 已暫停 (restore 檔: %s)" % (sid, os.path.basename(restore)))
            return True

        # hashcat 自然結束
        pw = None
        if rc == 0:
            pw = check_crack(self.app.hf)
        if pw:
            st["cracked"] = True
            st["password"] = pw
            stages[str(sid)] = {"status": "done", "progress": "100%"}
            save_state(st)
            try:
                with open(RESULT + r"\CRACKED_%s.txt" % self.app.ssid, "w",
                          encoding="utf-8") as f:
                    f.write("SSID: %s\nPASSPHRASE: %s\n" % (self.app.ssid, pw))
            except Exception:
                pass
            self.cracked_pw = pw
            self.log("🎉 破解成功! 密碼: %s" % pw)
            return False
        elif rc == 1:
            stages[str(sid)] = {"status": "exhausted",
                                "progress": stages.get(str(sid), {}).get("progress")}
            save_state(st)
            self.log("✔ 階段 %d 完成 (無解)" % sid)
            return False
        else:
            # 意外死亡 (GPU 錯誤等) → 當暫停處理，restore 檔仍在
            stages[str(sid)] = {"status": "paused",
                                "progress": stages.get(str(sid), {}).get("progress")}
            save_state(st)
            self.log("⚠ 階段 %d 意外結束 (rc=%s)，當暫停處理 — 按「繼續」重試" % (sid, rc))
            return True

    def parse_status(self, line):
        m = RE_SPEED.search(line)
        if m:
            self.status["speed"] = m.group(1) + " " + m.group(2)
        m = RE_PROG.search(line)
        if m:
            done, total = int(m.group(1)), int(m.group(2))
            pct = (100.0 * done / total) if total else 0.0
            self.status["progress"] = "%d / %d (%.2f%%)" % (done, total, pct)
            self.status["progress_pct"] = pct
        m = RE_RESTORE.search(line)
        if m:
            self.status["restore"] = m.group(1) + " / " + m.group(2)
        m = RE_ELAPSED.search(line)
        if m:
            self.status["elapsed"] = m.group(1)
            if self.status.get("eta"):
                try:
                    self.status["total"] = fmt_dur(dur_to_sec(self.status["elapsed"])
                                                   + dur_to_sec(self.status["eta"]))
                except Exception:
                    pass
        m = RE_ETA.search(line)
        if m:
            self.status["eta"] = m.group(1)
            if self.status.get("elapsed"):
                try:
                    self.status["total"] = fmt_dur(dur_to_sec(self.status["elapsed"])
                                                   + dur_to_sec(self.status["eta"]))
                except Exception:
                    pass
        m = RE_HWMON.search(line)
        if m:
            self.status["hwmon"] = "Temp:%sc Fan:%s%%" % (m.group(1), m.group(2))
        m = RE_STATUS.search(line)
        if m:
            self.status["state"] = m.group(1)
        m = RE_REJECT.search(line)
        if m:
            self.status["rejected"] = m.group(1) + " / " + m.group(2)

# =====================================================================
#  GUI
# =====================================================================
class App:
    def __init__(self):
        # 單執行例鎖
        if not self.acquire_lock():
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("WiFi 破解", "App 已在執行中 (gui.lock 未釋放)")
            root.destroy()
            sys.exit(0)

        os.makedirs(RESULT, exist_ok=True)
        os.makedirs(INBOX, exist_ok=True)

        self.hf = find_hashfile()
        self.ssid = extract_ssid(self.hf) or "32H10F"
        ensure_rockyou()

        self.root = tk.Tk()
        self.root.title("WiFi 破解 — %s (PMKID 22000)" % self.ssid)
        self.root.geometry("860x640")
        self.root.minsize(720, 520)

        st = load_state()
        if st is None:
            st = default_state(self.ssid)
            save_state(st)
        self.st = st
        if st.get("ssid") != self.ssid and st.get("stages", {}).get("1", {}).get("status") != "exhausted":
            st["ssid"] = self.ssid
            save_state(st)

        # 排程設定 (持久化在 state.json; 預設 23:00→06:30 不跑破解)
        sched = st.get("schedule") or {}
        self.schedule = {"enabled": sched.get("enabled", True),
                         "start": sched.get("start", "23:00"),
                         "end": sched.get("end", "06:30")}
        self.st["schedule"] = self.schedule
        save_state(st)
        self._sched_paused = False
        self.worker = Worker(self)
        self.build_ui()
        self.update_sched_label()
        self.worker.start()
        self.root.after(1000, self.check_schedule)

        # GPU 搶佔警告 (tasklist CSV: "name","pid","...")
        self._my_pid = str(os.getpid())
        stale = []
        for line in running_processes():
            parts = [p.strip().strip('"') for p in line.split(",")]
            if len(parts) >= 2 and parts[1] == self._my_pid:
                continue
            stale.append(line)
        if any("hashcat" in p.lower() for p in stale):
            self.log("⚠ 偵測到其他 hashcat 執行中 (可能搶佔 GPU):")
            for p in stale:
                self.log("   " + p)
        else:
            self.log("啟動: SSID=%s hash=%s gear=%d%%" % (self.ssid, self.hf, st.get("gear", 80)))
        if st.get("cracked"):
            self.log("🎉 已破解! 密碼: %s" % st.get("password"))

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.poll()

        self.root.mainloop()

    # ---------- 鎖 ----------
    def acquire_lock(self):
        try:
            f = open(LOCK, "x", encoding="utf-8")
            f.write(str(os.getpid()))
            f.close()
            return True
        except FileExistsError:
            old = 0
            try:
                old = int(open(LOCK, "r", encoding="utf-8").read().strip() or 0)
            except Exception:
                pass
            if old and is_pid_alive(old):
                return False
            try:
                os.remove(LOCK)
            except Exception:
                pass
            try:
                f = open(LOCK, "x", encoding="utf-8")
                f.write(str(os.getpid()))
                f.close()
                return True
            except Exception:
                return False

    def release_lock(self):
        try:
            os.remove(LOCK)
        except Exception:
            pass

    # ---------- UI ----------
    def build_ui(self):
        pad = {"padx": 8, "pady": 4}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="SSID: %s" % self.ssid, font=("Microsoft JhengHei", 13, "bold")).pack(side="left")
        self.ssid_label = ttk.Label(top, text="", foreground="#555")
        self.ssid_label.pack(side="left", padx=10)

        # 階段表
        self.tree = ttk.Treeview(self.root, columns=("stage", "status", "progress"),
                                 show="headings", height=5)
        self.tree.column("stage", width=330, anchor="w")
        self.tree.column("status", width=120, anchor="center")
        self.tree.column("progress", width=340, anchor="w")
        self.tree.heading("stage", text="階段")
        self.tree.heading("status", text="狀態")
        self.tree.heading("progress", text="進度")
        self.tree.pack(fill="x", **pad)

        # 即時狀態
        mid = ttk.Frame(self.root)
        mid.pack(fill="x", **pad)
        self.speed_var = tk.StringVar(value="Speed: —")
        self.prog_var = tk.StringVar(value="Progress: —")
        self.rest_var = tk.StringVar(value="Restore.Point: —")
        self.time_var = tk.StringVar(value="Elapsed: —")
        ttk.Label(mid, textvariable=self.speed_var, font=("Consolas", 11, "bold")).pack(side="left")
        ttk.Label(mid, textvariable=self.prog_var, font=("Consolas", 11, "bold")).pack(side="left", padx=16)
        ttk.Label(mid, textvariable=self.rest_var, font=("Consolas", 10)).pack(side="left", padx=16)
        ttk.Label(mid, textvariable=self.time_var, font=("Consolas", 10)).pack(side="left", padx=16)

        # 時間預估 + GPU 即時資訊 (nvidia-smi)
        mid2 = ttk.Frame(self.root)
        mid2.pack(fill="x", **pad)
        self.eta_var = tk.StringVar(value="Est. Remaining: —")
        ttk.Label(mid2, textvariable=self.eta_var,
                  font=("Consolas", 10, "bold"), foreground="#a60").pack(side="left")
        self.gpu_var = tk.StringVar(value="GPU: — | VRAM: —")
        ttk.Label(mid2, textvariable=self.gpu_var,
                  font=("Consolas", 10, "bold"), foreground="#06c").pack(side="left", padx=16)
        self.gpu_info = {}
        threading.Thread(target=self._gpu_poller, daemon=True).start()

        # 日誌
        self.logbox = ScrolledText(self.root, height=14, font=("Consolas", 9),
                                   state="disabled", background="#1e1e1e",
                                   foreground="#d4d4d4")
        self.logbox.pack(fill="both", expand=True, **pad)

        # 按鈕列
        btn = ttk.Frame(self.root)
        btn.pack(fill="x", **pad)
        self.pause_btn = ttk.Button(btn, text="⏸ 暫停", width=10, command=self.on_pause)
        self.pause_btn.pack(side="left")
        self.resume_btn = ttk.Button(btn, text="▶ 繼續", width=10, command=self.on_resume,
                                     state="disabled")
        self.resume_btn.pack(side="left", padx=6)

        # 排程 (免跑時段, 自動暫停/恢復)
        self.sched_label = ttk.Label(btn, text="🕒 —", foreground="#06c")
        self.sched_label.pack(side="left", padx=(16, 4))
        ttk.Button(btn, text="排程", width=6,
                   command=self.on_schedule_dialog).pack(side="left")

        self.state_label = ttk.Label(btn, text="", foreground="#080")
        self.state_label.pack(side="right")

        # 初始階段表
        self.refresh_tree()

    def log(self, text):
        """主執行緒呼叫 (poll / 事件回呼)."""
        self.logbox.configure(state="normal")
        self.logbox.insert("end", text + "\n")
        if int(self.logbox.index("end-1c").split(".")[0]) > 4000:
            self.logbox.delete("1.0", "1000.0")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    # ---------- 事件 ----------
    def on_pause(self):
        if self.worker and self.worker.is_running_hashcat():
            self.worker.pause_evt.set()
            self.pause_btn.configure(state="disabled")
            self.resume_btn.configure(state="disabled")  # worker 停下後才啟用
            self.state_label.configure(text="暫停中...", foreground="#a60")

    def on_resume(self):
        if self.worker:
            self.worker.resume_evt.set()
            self.resume_btn.configure(state="disabled")
            self.state_label.configure(text="重新啟動中...", foreground="#080")

    def on_close(self):
        w = self.worker
        if w and w.is_alive():
            if w.is_running_hashcat():
                ok = messagebox.askokcancel(
                    "離開", "hashcat 執行中。\n\n「確定」= 暫停並離開 (重開自動繼續)\n「取消」= 留在視窗")
                if not ok:
                    return
                w.pause_evt.set()
                w.join(timeout=20)
            else:
                w.stop_evt.set()
                w.join(timeout=5)
            if w.is_alive():
                try:
                    if w.proc:
                        w.proc.kill()
                except Exception:
                    pass
                w.stop_evt.set()
                w.join(timeout=5)
        self.release_lock()
        self.root.destroy()

    # ---------- GPU 即時資訊 (nvidia-smi, 每 3 秒) ----------
    def _gpu_poller(self):
        while True:
            try:
                r = subprocess.run(
                    ["nvidia-smi",
                     "--query-gpu=utilization.gpu,memory.used,memory.total,power.draw",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, timeout=8,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                p = [x.strip() for x in r.stdout.decode().split(",")]
                self.gpu_info = {
                    "util": int(p[0]),
                    "used": int(p[1]),
                    "total": int(p[2]),
                    "power": float(p[3]),
                }
            except Exception:
                pass
            time.sleep(3)

    # ---------- 輪詢 ----------
    def poll(self):
        try:
            # 日誌佇列
            drained = 0
            while drained < 500:
                try:
                    item = self.worker.log_q.get_nowait()
                except queue.Empty:
                    break
                drained += 1
                if isinstance(item, tuple):
                    kind, data = item
                    if kind == "__fatal__":
                        self.log("❌ 錯誤:\n" + data)
                        messagebox.showerror("WiFi 破解 — 錯誤", data)
                        self.worker.stop_evt.set()
                        self.release_lock()
                        self.root.destroy()
                        return
                    elif kind == "__done__":
                        self.state_label.configure(text="完成", foreground="#080")
                        self.pause_btn.configure(state="disabled")
                        self.resume_btn.configure(state="disabled")
                else:
                    self.log(item)

            # 狀態行
            s = self.worker.status
            if s.get("speed"):
                self.speed_var.set("Speed: %s" % s["speed"])
            if s.get("progress"):
                self.prog_var.set("Progress: %s" % s["progress"])
            if s.get("restore"):
                self.rest_var.set("Restore.Point: %s" % s["restore"])
            if s.get("elapsed"):
                self.time_var.set("Elapsed: %s" % s["elapsed"])
            if s.get("eta"):
                tot = (" | Est. Total: %s" % s["total"]) if s.get("total") else ""
                self.eta_var.set("Est. Remaining: %s%s" % (s["eta"], tot))
            g = self.gpu_info
            if g:
                hw = s.get("hwmon", "")
                self.gpu_var.set(
                    "GPU %d%% | VRAM %.1f/%.1f GB | %.0fW %s" % (
                        g["util"], g["used"] / 1024.0, g["total"] / 1024.0,
                        g["power"], hw))

            # 按鈕狀態
            running = self.worker.is_running_hashcat()
            if running:
                self.pause_btn.configure(state="normal" if not self.worker.pause_evt.is_set() else "disabled")
                self.resume_btn.configure(state="disabled")
            else:
                st_now = load_state()
                paused_stage = None
                if st_now:
                    for sid, _, _, _ in STAGE_DEFS:
                        if st_now.get("stages", {}).get(str(sid), {}).get("status") == "paused":
                            paused_stage = sid
                            break
                if paused_stage and self.worker.is_alive() and not self.worker.cracked_pw:
                    self.resume_btn.configure(state="normal")
                    self.pause_btn.configure(state="disabled")
                    self.state_label.configure(text="已暫停 (階段 %d)" % paused_stage,
                                               foreground="#a60")
                else:
                    self.pause_btn.configure(state="normal" if self.worker.is_alive() else "disabled")
                    self.resume_btn.configure(state="disabled")

            # 破解結果
            if self.worker.cracked_pw:
                pw = self.worker.cracked_pw
                self.state_label.configure(text="🎉 已破解!", foreground="#080")
                self.ssid_label.configure(text="密碼: %s" % pw,
                                          foreground="#080", font=("Microsoft JhengHei", 13, "bold"))
                if not getattr(self, "_crack_msg", False):
                    self._crack_msg = True
                    def _popup():
                        messagebox.showinfo("🎉 WiFi 破解成功!",
                                            "SSID: %s\n\n密碼: %s" % (self.ssid, pw))
                    self.root.after(800, _popup)

            # 階段表 (每 ~2 秒)
            if not hasattr(self, "_last_tree") or time.time() - self._last_tree > 2:
                self._last_tree = time.time()
                self.refresh_tree()
        except Exception:
            self.log("❌ poll 錯誤:\n" + traceback.format_exc())

        self.root.after(250, self.poll)

    # ---------- 排程 (免跑時段: 自動暫停/恢復) ----------
    def _sched_in_range(self, now=None):
        now = now or time.strftime("%H:%M")
        start, end = self.schedule["start"], self.schedule["end"]
        return (start <= now < end) if start < end else (now >= start or now < end)

    def update_sched_label(self):
        if self.schedule["enabled"]:
            self.sched_label.configure(
                text="🕒 %s–%s 免跑" % (self.schedule["start"], self.schedule["end"]),
                foreground="#06c")
        else:
            self.sched_label.configure(text="🕒 排程關", foreground="#888")

    def on_schedule_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("排程 — 免跑破解時段")
        dlg.resizable(False, False)
        dlg.transient(self.root)

        en = tk.BooleanVar(value=self.schedule["enabled"])
        st_ = tk.StringVar(value=self.schedule["start"])
        en_ = tk.StringVar(value=self.schedule["end"])

        tk.Checkbutton(dlg, text="啟用自動暫停 (時段內不跑破解)",
                       variable=en).pack(anchor="w", padx=12, pady=(12, 6))
        frm = ttk.Frame(dlg); frm.pack(padx=12, pady=4)
        ttk.Label(frm, text="開始").pack(side="left")
        tk.Entry(frm, textvariable=st_, width=6, justify="center",
                 font=("Consolas", 11)).pack(side="left", padx=8)
        ttk.Label(frm, text="結束").pack(side="left")
        tk.Entry(frm, textvariable=en_, width=6, justify="center",
                 font=("Consolas", 11)).pack(side="left", padx=8)
        ttk.Label(frm, text="(HH:MM, 可跨午夜)").pack(side="left")

        def ok(_=None):
            if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", st_.get()):
                messagebox.showerror("排程", "開始時間格式要 HH:MM", parent=dlg); return
            if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", en_.get()):
                messagebox.showerror("排程", "結束時間格式要 HH:MM", parent=dlg); return
            self.schedule["enabled"] = bool(en.get())
            self.schedule["start"] = st_.get()
            self.schedule["end"] = en_.get()
            self.st["schedule"] = self.schedule
            save_state(self.st)
            self.update_sched_label()
            self.log("🕒 排程更新: enabled=%s %s→%s"
                     % (self.schedule["enabled"], self.schedule["start"],
                        self.schedule["end"]))
            dlg.destroy()

        b = ttk.Frame(dlg); b.pack(pady=10)
        ttk.Button(b, text="確定", command=ok).pack(side="left", padx=6)
        ttk.Button(b, text="取消", command=dlg.destroy).pack(side="left", padx=6)
        dlg.bind("<Return>", ok)

    def check_schedule(self):
        try:
            now = time.strftime("%H:%M")
            running = self.worker.is_running_hashcat()
            active = self.schedule["enabled"] and self._sched_in_range(now)
            if active and running:
                self.log("🕒 排程時間到 (自動暫停): %s" % now)
                self._sched_paused = True
                self.on_pause()
            elif not active and not running and self._sched_paused:
                # 排程結束, 或用戶把排程關掉了 → 釋放排程造成的暫停
                self._sched_paused = False
                self.log("🕒 排程時間結束 (自動恢復): %s" % now)
                self.on_resume()
        except Exception:
            self.log("❌ 排程錯誤:\n" + traceback.format_exc())
        self.root.after(60000, self.check_schedule)

    def refresh_tree(self):
        st = load_state() or self.st
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        status_zh = {"pending": "待執行", "running": "執行中", "paused": "已暫停",
                     "exhausted": "已完成(無解)", "done": "已破解"}
        for sid, label, _, _ in STAGE_DEFS:
            info = st.get("stages", {}).get(str(sid), {})
            status = info.get("status", "pending")
            prog = info.get("progress") or ""
            icon = {"pending": "·", "running": "▶", "paused": "⏸",
                    "exhausted": "✔", "done": "🎉"}.get(status, "·")
            if status == "running" and self.worker.is_running_hashcat() \
                    and self.worker.current_sid == sid:
                prog = self.worker.status.get("progress") or prog
            self.tree.insert("", "end", values=("  %s %s" % (icon, label),
                                                status_zh.get(status, status), prog))

# ---------- 例外钩 ----------
def _excepthook(exc_type, exc, tb):
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        with open(GUI_LOG, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
    except Exception:
        pass
    try:
        messagebox.showerror("WiFi 破解 — 錯誤", text)
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc, tb)

def _thread_excepthook(args):
    text = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    try:
        with open(GUI_LOG, "a", encoding="utf-8") as f:
            f.write("[%s] [thread %s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"),
                                               args.thread.name, text))
    except Exception:
        pass
    sys.__excepthook__(args.exc_type, args.exc_value, args.exc_traceback)

def main():
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook
    if not os.path.exists(HC):
        messagebox.showerror("WiFi 破解", "找不到 hashcat:\n" + HC)
        sys.exit(1)
    App()

if __name__ == "__main__":
    main()
