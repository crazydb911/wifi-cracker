import sys, importlib.util, threading, tempfile
spec = importlib.util.spec_from_file_location("app", r"C:\\Users\\crazydb911\\Documents\\deepseek\\mac_wifi_app_v2.py")
mm = importlib.util.module_from_spec(spec)
sys.modules["app"] = mm
try:
    spec.loader.exec_module(mm)
except SystemExit:
    pass
App = mm.App
mm.HASHSTORE = tempfile.mkdtemp()
CAP = []; EV = []
class FakeR:
    stdout = b"COLD24_DONE\nCOLDHARVEST_DONE\nCOLD5G_DONE\nCOLDSCAN_DONE\n"
    stderr = b""
    returncode = 0
def fake_run(cmd, **kw):
    CAP.append(kw.get("input", b"").decode("utf-8", "replace"))
    return FakeR()
mm.subprocess.run = fake_run
class S:
    _cap_lock = threading.Lock()
    aps = []; aps_seen = {}; _preheat = False; _last_pow = None
    target = None
    hash_pool = set()
    _running = threading.Event()
    def _traffic_bssids(self): return set()
    def _ch_w(self, n, g, t): return n
    def _ev(self, k, msg): EV.append((k, msg))
    def _log(self, x): EV.append(("log", x))
    def _enqueue_sweep_hits(self, new): pass
    def set_phase(self, *a, **k): pass
S._sweep_round = App._sweep_round
s = S(); CAP.clear(); EV.clear()
r = s._sweep_round()
sc = CAP[0] if CAP else ""
print("rc=%s len=%d" % (r, len(sc)))
hc = [i for i in range(len(sc)) if sc.startswith("hcxdumptool", i)]
cv = [i for i in range(len(sc)) if sc.startswith("timeout 20 hcxpcapngtool", i)]
tx0 = sc.find("TXRX0 "); tx1 = sc.find("TXRX1 ")
ok = []
ok.append(("E1  3 hcxdumptool starts", sc.count("hcxdumptool -i wlan0") == 3))
ok.append(("E2  2.4G channel list", "-c 1a,6a,11a" in sc))
ok.append(("E3  5G channel list", "-c 36b,40b,44b,48b" in sc))
ok.append(("E4  rcascan=active x2", sc.count("--rcascan=active") == 2))
ok.append(("E5  exitoneapol=1 x1", sc.count("--exitoneapol=1") == 1))
ok.append(("E6  errormax raised x3", sc.count("--errormax=100000") == 3))
ok.append(("E7  no per-ch tcpdump", "tcpdump -i wlan0" not in sc))
ok.append(("E8  no per-ch set chan", "iw dev wlan0 set channel" not in sc))
ok.append(("E9  3 converters", len(cv) == 3))
ok.append(("E10 --rdt x3", sc.count("--rdt") == 3))
ok.append(("E11 distinct out files",
        all(("-w /tmp/cold%d.pcapng " % k) in sc for k in (1, 2, 3))))
ok.append(("E12 no bare cold.pcapng", "-w /tmp/cold.pcapng " not in sc))
ok.append(("E13 cleanup first", sc.index("rm -f /tmp/cold*") < min(hc)))
ok.append(("E14 TXRX0 before all caps", tx0 >= 0 and tx0 < min(hc)))
ok.append(("E15 TXRX1 after all caps", tx1 > max(hc)))
ok.append(("E16 TXRX1 before its own convert", tx1 < max(cv)))
ok.append(("E16b cap3 < TXRX1 < convert3", hc[2] < tx1 < cv[2]))
ok.append(("E17 each cap converted",
        all(any(c > h for c in cv) for h in hc)))
ok.append(("E18 3 cats", sc.count("cat /tmp/cold") == 3))
ok.append(("E19 4 markers", sum(sc.count(x) for x in
        ["COLD24_DONE", "COLDHARVEST_DONE", "COLD5G_DONE",
         "COLDSCAN_DONE"]) == 4))
ok.append(("E20 no literal %s", "%s" not in sc))
ok.append(("E21 no literal %d", "%d" not in sc))
ok.append(("E22 no SWEEPCH leftovers", "SWEEPCH" not in sc))
for n, v in ok:
    print("%-28s %s" % (n, "PASS" if v else "FAIL"))
print("")
print("ALL PASS" if all(v for _, v in ok) else "FAILURES: %s" %
      [n for n, v in ok if not v])
print("events:")
for k, v in EV: print("  %s: %s" % (k, str(v)[:95]))