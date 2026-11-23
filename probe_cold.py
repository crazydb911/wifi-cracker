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
S._pull_guest_caps = App._pull_guest_caps
s = S(); CAP.clear(); EV.clear()
r = s._sweep_round()
sc = CAP[0] if CAP else ""
print("rc=%s len=%d" % (r, len(sc)))
hc = [i for i in range(len(sc)) if sc.startswith("hcxdumptool", i)]
cv = [i for i in range(len(sc)) if sc.startswith("timeout 15 hcxpcapngtool", i)]
tx0 = sc.find("TXRX0 "); tx1 = sc.find("TXRX1 ")
ok = []
# E0 is the regression guard for a real bug: hcxdumptool.c calls
# exit(EXIT_FAILURE) when --rcascan and -w appear together, in both option
# orders. A cold round that paired them captured nothing and the reporting
# would have reported a dead radio for the tool's own argument check.
inv = []
for i in hc:
    j = sc.find("\n", i)
    inv.append(sc[i:j if j > 0 else len(sc)])
ok.append(("E0  no --rcascan with -w",
          not any(("--rcascan" in x and " -w " in x) for x in inv)))
ok.append(("E1  4 hcxdumptool starts", sc.count("hcxdumptool -i wlan0") == 4))
ok.append(("E2  2.4G channel list", "-c 1a,6a,11a" in sc))
ok.append(("E3  5G channel list", "-c 36b,40b,44b,48b" in sc))
ok.append(("E4  rcascan=active x2", sc.count("--rcascan=active") == 2))
ok.append(("E5  exitoneapol=1 x2", sc.count("--exitoneapol=1") == 2))
ok.append(("E6  errormax raised x4", sc.count("--errormax=100000") == 4))
ok.append(("E7  no per-ch tcpdump", "tcpdump -i wlan0" not in sc))
ok.append(("E8  no per-ch set chan", "iw dev wlan0 set channel" not in sc))
ok.append(("E9  2 converters", len(cv) == 2))
ok.append(("E10 --rdt x4", sc.count("--rdt") == 4))
ok.append(("E11 distinct out files",
          sorted(set(__import__("re").findall(r"cold(\d+)\.pcapng", sc))) == ["1", "2"]))
ok.append(("E12 no bare cold.pcapng", "cold.pcapng" not in sc.replace("cold1.pcapng", "").replace("cold2.pcapng", "")))
ok.append(("E13 cleanup first", sc.index("rm -f /tmp/cold*") < min(hc)))
ok.append(("E14 TXRX0 before all caps", tx0 >= 0 and tx0 < min(hc)))
ok.append(("E15 TXRX1 after both harvests", tx1 > max(sc.index("-w /tmp/cold1.pcapng"), sc.index("-w /tmp/cold2.pcapng"))))
ok.append(("E16 harvest24 before harvest5g",
          sc.index("-w /tmp/cold1.pcapng") < sc.index("-w /tmp/cold2.pcapng")))
ok.append(("E16b cap2 < TXRX1 < convert2",
          sc.index("-w /tmp/cold2.pcapng") < tx1 < cv[1]))
ok.append(("E17 each harvest converted",
          cv[0] > sc.index("-w /tmp/cold1.pcapng") and cv[1] > sc.index("-w /tmp/cold2.pcapng")))
ok.append(("E18 2 cats", sc.count("cat /tmp/cold") == 2))
ok.append(("E19 7 markers",
          all(m in sc for m in ("COLD24_DONE", "COLD5G_DONE", "RCASCAN24_START",
                                "RCASCAN24_DONE", "RCASCAN5G_START",
                                "RCASCAN5G_DONE", "COLDSCAN_DONE"))))
ok.append(("E20 no literal %s", "%s" not in sc))
ok.append(("E21 no literal %d", "%d" not in sc))
ok.append(("E22 no SWEEPCH leftovers", "SWEEPCH" not in sc))
# asset before diagnosis: a PMKID already proves transmit works, so the
# rcascan verdict only has to separate a dead radio from an empty room.
ok.append(("E23 both harvests before both rcascan",
          max(sc.index("-w /tmp/cold1.pcapng"), sc.index("-w /tmp/cold2.pcapng"))
          < min(i for i in range(len(sc)) if sc.startswith("echo RCASCAN24_START", i))))
ok.append(("E24 rcascan phases carry no -w",
          all(" -w " not in x for x in inv if "--rcascan" in x)))
ok.append(("E25 rcascan carries --rds=5",
          all("--rds=5" in x for x in inv if "--rcascan" in x)))
ok.append(("E26 harvest carries --rds=4",
          all("--rds=4" in x for x in inv if " -w " in x)))
ok.append(("E27 cold budget inside ssh timeout", r is not None and r <= 220))
for n, p in ok:
    print("%-34s %s" % (n, "PASS" if p else "FAIL"))
bad = [n for n, p in ok if not p]
print("\nFAILURES:", bad if bad else "none")
print("invocations found:", len(inv))
for x in inv:
    print("  |", x[:150])
