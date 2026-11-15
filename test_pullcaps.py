import sys, importlib.util, os, glob, subprocess, time
spec = importlib.util.spec_from_file_location("app", "/Users/tongbao/wifi_cracker/mac_wifi_app_v2.py")
mm = importlib.util.module_from_spec(spec); sys.modules["app"] = mm
try: spec.loader.exec_module(mm)
except SystemExit: pass
App = mm.App
VM = mm.VM_SSH.split()
print("CAPSTORE =", mm.CAPSTORE)
print("VM_SSH   =", mm.VM_SSH)

def gsh(cmd, t=60):
    return subprocess.run(VM + ["sh", "-s"], input=(cmd + "\n").encode(), capture_output=True, timeout=t)

# real 5 KB of noise with a pcapng magic header so it looks like a capture
mk = ("printf '\\x0a\\x0d\\x0d\\x0a' > /newroot/tmp/coldTEST.pcapng; "
      "dd if=/dev/urandom bs=1024 count=5 >> /newroot/tmp/coldTEST.pcapng 2>/dev/null; "
      "cp /newroot/tmp/coldTEST.pcapng /newroot/tmp/coldTEST.pcapng_1; "
      "printf 'tiny' > /newroot/tmp/coldTINY.pcapng; "
      "ls -l /newroot/tmp/cold*.pcapng*")
r = gsh(mk)
print("--- seeded in guest ---")
print(r.stdout.decode("utf-8", "replace").strip() or r.stderr.decode()[:200])

class S:
    def _ev(self, kind, msg): print("   EVENT [%s] %s" % (kind, msg))
S._pull_guest_caps = App._pull_guest_caps

print("--- run 1: two real files + one too-small ---")
S._pull_guest_caps(S(), "/newroot/tmp/cold*.pcapng*", "cold")

before = sorted(glob.glob(mm.CAPSTORE + "/cold-*TEST*"))
print("landed on Mac:", [os.path.basename(x) for x in before])
for f in before:
    print("   size=%d head=%s" % (os.path.getsize(f), open(f, "rb").read(4).hex()))
left = gsh("ls /newroot/tmp/cold*.pcapng* 2>/dev/null").stdout.decode().strip()
print("still in guest:", repr(left))

print("--- run 2: guest already empty, must say 0 of 0 and not crash ---")
S._pull_guest_caps(S(), "/newroot/tmp/cold*.pcapng*", "cold")

print("--- run 3: pattern matching nothing at all ---")
S._pull_guest_caps(S(), "/newroot/tmp/nothinghere*.pcapng*", "cold")

for f in before:
    os.remove(f)
print("cleaned test artifacts:", len(before))
