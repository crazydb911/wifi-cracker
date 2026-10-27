"""插回 DWA-160 後的一鍵實彈驗證: 5G主動射頻 + BPF定向, 對比基線."""
import paramiko, sys

C = paramiko.SSHClient()
C.set_missing_host_key_policy(paramiko.AutoAddPolicy())
C.connect("100.64.239.76", username="tongbao",
          key_filename=r"C:\Users\crazydb911\.ssh\opremote_ed25519",
          timeout=25, banner_timeout=90, auth_timeout=90)

def sh(cmd, t=120):
    i, o, e = C.exec_command(cmd, timeout=t)
    return (o.read().decode("utf-8", "replace").strip(),
            e.read().decode("utf-8", "replace").strip())

VM = ("ssh -i /Users/tongbao/.ssh/vm_tongbao -p 2222 "
      "-o StrictHostKeyChecking=no -o BatchMode=yes root@127.0.0.1")

u, _ = sh("ioreg -r -c IOUSBHostDevice 2>/dev/null | grep -c IOUSBHostDevice")
print("USB devices:", u)
if u.strip() in ("0", ""):
    print("!! 網卡不在 USB 总線, 先拔插")
    sys.exit(1)
p, _ = sh(VM + " ls /sys/class/ieee80211/", t=30)
print("VM phy:", p or "!! 缺卡(等QEMU自動重抓, 或重啟app)")
if not p:
    sys.exit(1)

i, o, e = C.exec_command(VM + " sh -s", timeout=400)
script = """CH="chroot /newroot "
$CH iw reg get | sed -n 2p
$CH ifconfig wlan0 down 2>/dev/null; sleep 1
$CH iw dev wlan0 set type monitor 2>/dev/null
$CH ifconfig wlan0 up 2>/dev/null; sleep 1
echo ===BPF===
$CH tcpdump -y IEEE802_11 -dd "wlan addr1 bc:3e:07:01:dc:98 or wlan addr2 bc:3e:07:01:dc:98 or wlan addr3 bc:3e:07:01:dc:98 or type mgt subtype probereq" > /tmp/t.bpf 2>/dev/null
wc -c < /tmp/t.bpf
echo ===RC36B===
timeout 18 $CH hcxdumptool -i wlan0 -c 36b --rcascan=active 2>&1 | grep -aE "PROBERESPONSE|BEACON" | head -3
echo ===RC44B===
timeout 18 $CH hcxdumptool -i wlan0 -c 44b --rcascan=active 2>&1 | grep -aE "PROBERESPONSE|BEACON" | head -3
echo ===RC36B-RESP===
timeout 25 $CH hcxdumptool -i wlan0 -c 36b --rcascan=active 2>&1 | grep -aE "PROBERESPONSE|received" | tail -4
echo ===ATK36B===
timeout 32 $CH hcxdumptool -i wlan0 -c 36b -w /tmp/a36.pcapng -t 5 --rds=2 2>&1 | tail -6
ls -la /tmp/a36* 2>/dev/null
$CH hcxpcapngtool --all -o /tmp/a36.22000 /tmp/a36.pcapng* 2>/dev/null
echo 36B: PMKID=$($CH grep -c PMKID /tmp/a36.22000 2>/dev/null) HS=$($CH grep -c EAPOL /tmp/a36.22000 2>/dev/null)
$CH rm -f /tmp/a36*
echo ===ATK1_BPF===
timeout 32 $CH hcxdumptool -i wlan0 -c 1a --bpf=/tmp/t.bpf -w /tmp/a1.pcapng -t 7 --rds=2 2>&1 | tail -6
ls -la /tmp/a1* 2>/dev/null
$CH hcxpcapngtool --all -o /tmp/a1.22000 /tmp/a1.pcapng* 2>/dev/null
echo 1BPF: PMKID=$($CH grep -c PMKID /tmp/a1.22000 2>/dev/null) HS=$($CH grep -c EAPOL /tmp/a1.22000 2>/dev/null)
$CH rm -f /tmp/a1* /tmp/t.bpf
"""
i.write(script)
i.flush()
i.channel.shutdown_write()
print(o.read().decode("utf-8", "replace")[:1500])
C.close()
