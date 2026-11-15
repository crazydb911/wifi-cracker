import sys, importlib.util, time
spec = importlib.util.spec_from_file_location("app", "/Users/tongbao/wifi_cracker/mac_wifi_app_v2.py")
mm = importlib.util.module_from_spec(spec)
sys.modules["app"] = mm
try:
    spec.loader.exec_module(mm)
except SystemExit:
    pass
print("CAP_BACKUP_DIR =", mm.CAP_BACKUP_DIR)
print("key exists     =", __import__("os").path.exists(mm.CAP_BACKUP_KEY))
EV = []
class S:
    def _ev(self, k, msg): EV.append((k, msg)); print("  EV %s: %s" % (k, msg))
s = S()
t0 = time.time()
S._cap_backup_once = mm.App._cap_backup_once
s._cap_backup_once()
print("elapsed=%.1fs" % (time.time() - t0))