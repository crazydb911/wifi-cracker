"""macctl — robust control of the target Mac over SSH despite IP drift + randomized MAC.

Usage (from C:\\Users\\crazydb911\\Documents\\deepseek):
    python macctl.py                      # discover + print IP, keep state
    python macctl.py "tail -5 /tmp/cap56.log"   # discover + run a command
    python macctl.py --sweep              # force full sweep (ignore cached IP)

State: mac_state.json holds last known IP for fast reconnect.
The Mac is identified by the ONLY host that accepts SSH user 'tongbao'.
"""
import subprocess, time, json, os, sys
import paramiko

USER, PW = "tongbao", "240628"
SUDO_PW = "240628"
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mac_state.json")
KNOWN_NON_MAC = {103,104,107,108,112,113,114,115,120}

def _load_state():
    try:
        with open(STATE) as f: return json.load(f)
    except Exception:
        return {}

def _save_state(d):
    with open(STATE,"w") as f: json.dump(d,f)

def ping(ip):
    try:
        subprocess.run(["ping","-n","1","-w","700",ip],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, check=True)
        return True
    except Exception:
        return False

def _ssh(ip):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(ip, username=USER, password=PW, timeout=5,
                  allow_agent=False, look_for_keys=False, banner_timeout=8, auth_timeout=8)
        return c
    except Exception:
        return None

def _up_hosts():
    procs = {}
    for i in range(2,255):
        ip=f"192.168.1.{i}"
        procs[i]=subprocess.Popen(["ping","-n","1","-w","700",ip],
                                  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    up=[i for i,p in procs.items() if p.wait(timeout=4)==0]
    return up

def discover(force_sweep=False):
    """Return (ip, ssh_client) for the Mac. Try cached IP first, then sweep."""
    st=_load_state()
    order=[]
    if not force_sweep and st.get("ip"):
        order.append(st["ip"].split(".")[-1])
    up=_up_hosts()
    # candidates: cached first, then unknown (non-known) hosts, then known hosts
    for i in up:
        ip=f"192.168.1.{i}"
        if ip not in order:
            order.append(ip)
    order.sort(key=lambda ip: (0 if ip in [f"192.168.1.{x}" for x in (st.get("ip","").split(".")[-1:] if st.get("ip") else [])] else 1,
                                (int(ip.split('.')[-1]) in KNOWN_NON_MAC)))
    for ip in order:
        c=_ssh(ip)
        if c:
            st["ip"]=ip; st["ts"]=time.time(); _save_state(st)
            return ip,c
    return None,None

def run(client, cmd, use_sudo=False):
    full = ("echo %s | sudo -S sh -c '%s'" % (SUDO_PW, cmd.replace("'", "'\\''"))) if use_sudo else cmd
    _,out,err=client.exec_command(full,timeout=40)
    return out.read().decode("utf-8","replace")+err.read().decode("utf-8","replace")

if __name__=="__main__":
    args=sys.argv[1:]
    force = "--sweep" in args
    args=[a for a in args if a!="--sweep"]
    ip,c=discover(force)
    if not c:
        print("MAC_NOT_FOUND"); sys.exit(2)
    print("MAC_IP=%s"%ip)
    if args:
        out=run(c,args[0])
        print(out)
