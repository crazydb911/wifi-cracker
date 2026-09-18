#!/bin/bash
# Rebuild the DWA-160 capture VM on the Mac (recipe = 2026-09-13 proven build).
# v3.24 netboot lts kernel = 6.18.35-0-lts (same as original build).
set -u
B=/tmp/vmbuild
mkdir -p $B/boot $B/irfs $B/modloop $B/apks
log(){ echo "[$(date +%H:%M:%S)] $*" >> /tmp/vmbuild/build.log; }
exec > >(tee -a /tmp/vmbuild/build.log) 2>&1
log "===== REBUILD START ====="

# ---------- S1: netboot files ----------
log "S1: download v3.24 netboot lts files"
NB=https://dl-cdn.alpinelinux.org/alpine/v3.24/releases/aarch64/netboot
for f in vmlinuz-lts initramfs-lts modloop-lts; do
  if [ -s $B/boot/$f ]; then log "keep existing $f"; continue; fi
  curl -sSfL -o $B/boot/$f $NB/$f || { log "FAIL download $f"; exit 1; }
  log "got $f ($(du -h $B/boot/$f | cut -f1))"
done

# ---------- S2: unpack initramfs + modloop ----------
log "S2: unpack initramfs-lts + modloop-lts"
rm -rf $B/irfs; mkdir -p $B/irfs
( cd $B/irfs && gunzip -c $B/boot/initramfs-lts | cpio -idm >/dev/null 2>&1 ) || { log "FAIL initramfs extract"; exit 1; }
# macOS cpio drops most symlinks -> restore from archive with python parser
/usr/bin/python3 /tmp/cpio_fixlinks.py $B/irfs $B/boot/initramfs-lts | tee -a /tmp/vmbuild/build.log
rm -rf $B/modloop; mkdir -p $B/modloop
/opt/homebrew/bin/unsquashfs -f -d $B/modloop $B/boot/modloop-lts >/dev/null 2>&1 || \
  ( cd $B/modloop && ( /opt/homebrew/bin/zstd -dc $B/boot/modloop-lts 2>/dev/null || gunzip -c $B/boot/modloop-lts ) | cpio -idm >/dev/null 2>&1 ) || log "WARN modloop extract"
if [ ! -d $B/modloop/modules ] && [ -f /tmp/vmbuild.tar ]; then
  mkdir -p $B/modloop && tar -xf /tmp/vmbuild.tar -C $B/modloop
  log "modloop extracted from /tmp/vmbuild.tar"
elif [ ! -d $B/modloop/modules ]; then
  log "FAIL modloop extract (no modules dir, no tar)"; exit 1
fi
KV=$(ls $B/modloop/modules 2>/dev/null | head -1); [ -z "$KV" ] && KV=$(ls $B/modloop 2>/dev/null | head -1)
log "kernel modules dir: $KV"
# targeted module copies only (keep initrd small; modloop full tree = 256MB -> ENOSPC)
MDEST=$B/irfs/lib/modules/$KV
mkdir -p $MDEST
for d in \
  kernel/crypto \
  kernel/lib/crypto \
  kernel/lib/crc \
  kernel/net/core \
  kernel/net/mac80211 \
  kernel/net/wireless \
  kernel/net/rfkill \
  kernel/net/packet \
  kernel/net/802 \
  kernel/drivers/net/wireless/ralink \
  kernel/drivers/usb \
  kernel/fs/ext4 \
  kernel/fs/jbd2 ; do
  SRC=$B/modloop/modules/$KV/$d
  [ -d "$SRC" ] || { log "WARN missing module dir $d"; continue; }
  mkdir -p $MDEST/$(dirname $d)
  cp -R "$SRC" $MDEST/$d 2>/dev/null && log "modules ok: $d" || log "WARN cp failed: $d"
done
for f in kernel/fs/mbcache.ko kernel/drivers/net/net_failover.ko; do
  SRC=$B/modloop/modules/$KV/$f
  [ -f "$SRC" ] || { log "WARN missing module $f"; continue; }
  cp "$SRC" $MDEST/$f && log "module ok: $f"
done

# ---------- S3: apk payloads into initramfs ----------
log "S3: extract apks (openssh/openssl/e2fsprogs) into initramfs"
IDX=$(curl -s https://dl-cdn.alpinelinux.org/alpine/v3.24/main/aarch64/ | grep -oE 'href="[^"]+\.apk"' | sed 's/href="//;s/"//')
for want in openssh- openssh-client- openssh-server- openssl- e2fsprogs- e2fsprogs-libs- libcom_err- apk-; do
  f=$(echo "$IDX" | grep "^${want}" | grep "\.apk" | head -1)
  if [ "$want" = "apk-" ]; then f=$(echo "$IDX" | grep -E "^apk-[0-9]" | head -1); fi
  [ -z "$f" ] && { log "WARN apk not listed: $want"; continue; }
  curl -sSfL -o $B/apks/$f https://dl-cdn.alpinelinux.org/alpine/v3.24/main/aarch64/$f || { log "FAIL apk $f"; continue; }
  tar -xJf $B/apks/$f -C $B/irfs && log "extracted $f"
done
# firmware
FW=$(find $B/modloop -name "rt2870.bin*" | head -1)
if [ -n "$FW" ]; then
  mkdir -p $B/irfs/lib/firmware
  case "$FW" in
    *.zst) /opt/homebrew/bin/zstd -d -f -q "$FW" -o $B/irfs/lib/firmware/rt2870.bin ;;
    *) cp "$FW" $B/irfs/lib/firmware/rt2870.bin ;;
  esac
  log "firmware ok: $FW"
else
  log "WARN: rt2870.bin not found in modloop"
fi
# ssh key
mkdir -p $B/irfs/root/.ssh
cp ~/.ssh/vm_tongbao.pub $B/irfs/root/.ssh/authorized_keys
chmod 700 $B/irfs/root/.ssh; chmod 600 $B/irfs/root/.ssh/authorized_keys
# sshd config (not in any openssh apk; alpine-conf would provide it in a full system)
mkdir -p $B/irfs/etc/ssh
[ -f $B/irfs/etc/ssh/sshd_config ] || printf 'PermitRootLogin yes\nPasswordAuthentication no\nPort 22\n' > $B/irfs/etc/ssh/sshd_config
# host keys generated on the Mac (arch-independent); no ssh-keygen needed in initramfs
for t in ed25519 ecdsa; do
  if [ ! -f $B/irfs/etc/ssh/ssh_host_${t}_key ]; then
    ssh-keygen -t $t -N '' -q -f $B/irfs/etc/ssh/ssh_host_${t}_key
  fi
done
chmod 600 $B/irfs/etc/ssh/ssh_host_*_key 2>/dev/null
# sshd privilege-separation user (required by openssh 9+)
grep -q '^sshd:' $B/irfs/etc/passwd 2>/dev/null || printf 'sshd:x:77:77:ssh daemon:/var/empty:/usr/sbin/nologin\n' >> $B/irfs/etc/passwd
grep -q '^sshd:' $B/irfs/etc/group 2>/dev/null || printf 'sshd:x:77:\n' >> $B/irfs/etc/group
mkdir -p $B/irfs/var/empty
log "sshd_config + host keys + sshd user ensured"
# ensure empty dirs for repack
mkdir -p $B/irfs/{proc,sys,dev,newroot,run,etc,root,usr}

# ---------- S4: /init + repack ----------
log "S4: write /init + repack initramfs"
cat > $B/irfs/init <<'INIT'
#!/bin/sh
export PATH=/sbin:/bin:/usr/sbin:/usr/bin
/bin/busybox --install -s 2>/dev/null
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev
mkdir -p /tmp
ln -sf /usr/bin/kmod /tmp/depmod
ln -sf /usr/bin/kmod /tmp/modprobe
KVER=$(uname -r)
M=/lib/modules/$KVER
insmod $M/kernel/drivers/virtio/virtio_pci_modern_dev.ko 2>/dev/null
insmod $M/kernel/drivers/virtio/virtio_pci_legacy_dev.ko 2>/dev/null
insmod $M/kernel/drivers/virtio/virtio_pci.ko 2>/dev/null
insmod $M/kernel/drivers/block/virtio_blk.ko 2>/dev/null
insmod $M/kernel/net/core/failover.ko 2>/dev/null
insmod $M/kernel/drivers/net/net_failover.ko 2>/dev/null
insmod $M/kernel/drivers/net/virtio_net.ko 2>/dev/null
insmod $M/kernel/lib/crc/crc16.ko 2>/dev/null
insmod $M/kernel/fs/mbcache.ko 2>/dev/null
insmod $M/kernel/fs/jbd2/jbd2.ko 2>/dev/null
insmod $M/kernel/fs/ext4/ext4.ko 2>/dev/null
insmod $M/kernel/drivers/usb/core/usbcore.ko 2>/dev/null
insmod $M/kernel/drivers/usb/host/xhci-hcd.ko 2>/dev/null
insmod $M/kernel/drivers/usb/host/xhci-pci.ko 2>/dev/null
insmod $M/kernel/net/packet/af_packet.ko 2>/dev/null
insmod $M/kernel/net/rfkill/rfkill.ko 2>/dev/null
insmod $M/kernel/net/wireless/cfg80211.ko 2>/dev/null
insmod $M/kernel/lib/crypto/libarc4.ko 2>/dev/null
insmod $M/kernel/lib/crc/crc-ccitt.ko 2>/dev/null
insmod $M/kernel/net/mac80211/mac80211.ko 2>/dev/null
date -s "2026-09-13 12:00:00" 2>/dev/null
i=0; while [ ! -b /dev/vda ] && [ $i -lt 90 ]; do sleep 1; i=$((i+1)); done
# format if unformatted (build mode)
if [ -b /dev/vda ] && ! blkid /dev/vda >/dev/null 2>&1; then
  echo ">> formatting /dev/vda ext4"
  /sbin/mke2fs -t ext4 -F /dev/vda || mke2fs -t ext4 -F /dev/vda
fi
[ -b /dev/vda ] && mount -t ext4 /dev/vda /newroot 2>/dev/null

# wifi driver: rebuild modules.dep, let modprobe resolve the ralink chain
/tmp/depmod -a $KVER 2>&1 | head -2
/tmp/modprobe rt2800usb 2>&1 | head -3
[ -d /sys/module/rt2800usb ] || { insmod $M/kernel/net/wireless/cfg80211.ko 2>/dev/null
  insmod $M/kernel/net/rfkill/rfkill.ko 2>/dev/null
  insmod $M/kernel/net/wireless/cfg80211.ko 2>/dev/null
  insmod $M/kernel/lib/crypto/libarc4.ko 2>/dev/null
  insmod $M/kernel/lib/crc/crc-ccitt.ko 2>/dev/null
  insmod $M/kernel/net/mac80211/mac80211.ko 2>/dev/null
  insmod $M/kernel/drivers/net/wireless/ralink/rt2x00/rt2x00lib.ko 2>/dev/null
  insmod $M/kernel/drivers/net/wireless/ralink/rt2x00/rt2500lib.ko 2>/dev/null
  insmod $M/kernel/drivers/net/wireless/ralink/rt2x00/rt2x00usb.ko 2>/dev/null
  insmod $M/kernel/drivers/net/wireless/ralink/rt2x00/rt2800lib.ko 2>/dev/null
  insmod $M/kernel/drivers/net/wireless/ralink/rt2x00/rt2800usb.ko 2>/dev/null; }
[ -f /lib/firmware/rt2870.bin ] && [ -d /newroot/lib/firmware ] && \
  cp -f /lib/firmware/rt2870.bin /newroot/lib/firmware/ 2>/dev/null
ifconfig eth0 up 2>/dev/null
ifconfig lo up 2>/dev/null
ifconfig lo 127.0.0.1 2>/dev/null
ifconfig eth0 10.0.2.15 netmask 255.255.255.0 2>/dev/null
i=0; while [ $i -lt 30 ]; do
  ifconfig eth0 2>/dev/null | grep -q "10.0.2.15" && break
  sleep 1; i=$((i+1))
done
route add default gw 10.0.2.2 2>/dev/null
echo "nameserver 1.1.1.1" > /etc/resolv.conf 2>/dev/null
# ssh host keys (initramfs copy)
mkdir -p /var/empty
chown 0:0 /var/empty 2>/dev/null; chmod 755 /var/empty 2>/dev/null
chown 0:0 /root /root/.ssh /root/.ssh/authorized_keys 2>/dev/null
chmod 700 /root/.ssh 2>/dev/null
chmod 600 /root/.ssh/authorized_keys 2>/dev/null
[ -f /etc/ssh/ssh_host_ed25519_key ] || ssh-keygen -A 2>&1 | head -3
[ -x /usr/sbin/sshd ] && /usr/sbin/sshd -o "ListenAddress=0.0.0.0" -o "PermitRootLogin=yes" 2>&1 | head -5 &
echo "initramfs sshd started"
if [ -x /newroot/sbin/init ]; then
  echo ">> populated rootfs detected: switch_root"
  chroot /newroot /usr/sbin/chpasswd 2>/dev/null <<'CHPW' || true
root:alpine123
CHPW
  exec switch_root /newroot /sbin/init
fi
echo ">> build mode: staying in initramfs shell (rootfs=/newroot)"
/bin/sh
INIT
chmod +x $B/irfs/init
if [ ! -x $B/irfs/bin/sh ] && [ ! -x $B/irfs/bin/busybox ]; then log "FAIL: no shell in initramfs tree"; exit 1; fi
cd $B/irfs && find . -print | cpio -o -H newc 2>/dev/null | gzip -9 > /tmp/initramfs-custom
log "initramfs-custom size: $(du -h /tmp/initramfs-custom | cut -f1)"
SZ=$(stat -f%z /tmp/initramfs-custom 2>/dev/null || stat -c%s /tmp/initramfs-custom)
[ "$SZ" -gt 900000000 ] && { log "FAIL: initrd too big ($SZ)"; exit 8; }
cp $B/boot/vmlinuz-lts /tmp/alpine-boot/boot/vmlinuz-lts 2>/dev/null || { mkdir -p /tmp/alpine-boot/boot; cp $B/boot/vmlinuz-lts /tmp/alpine-boot/boot/vmlinuz-lts; }

# ---------- S5: create raw vda + boot build VM ----------
log "S5: create 512M raw vda"
pkill -f qemu-system-aarch64 2>/dev/null; sleep 2
rm -f /tmp/alpine-root.raw /tmp/alpine-root.qcow2
dd if=/dev/zero of=/tmp/alpine-root.raw bs=1m count=512 status=none
/opt/homebrew/bin/qemu-img convert -f raw -O qcow2 /tmp/alpine-root.raw /tmp/alpine-root.qcow2
log "boot build VM"
rm -f /tmp/vm_app_serial.log /tmp/vm_app_monitor.sock
nohup /opt/homebrew/bin/qemu-system-aarch64 -machine virt -cpu cortex-a72 -m 4096 -smp 4 \
  -drive file=/tmp/alpine-root.qcow2,format=qcow2 \
  -kernel /tmp/alpine-boot/boot/vmlinuz-lts -initrd /tmp/initramfs-custom -append "console=ttyAMA0" \
  -chardev file,id=s0,path=/tmp/vm_app_serial.log,append=on -serial chardev:s0 \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:2222-10.0.2.15:22 \
  -device virtio-net-pci,netdev=n0 \
  -device qemu-xhci,id=xhci -device usb-host,bus=xhci.0,vendorid=0x148f,productid=0x5572 \
  -display none -monitor unix:/tmp/vm_app_monitor.sock,server,nowait >/dev/null 2>&1 &
log "qemu pid: $!"

VSSH="ssh -i $HOME/.ssh/vm_tongbao -p 2222 -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes root@127.0.0.1"
log "wait for VM ssh (build mode) ..."
ok=0
for i in $(seq 1 40); do
  if $VSSH "echo VM_SSH_OK; uname -r" 2>/dev/null | grep -q VM_SSH_OK; then ok=1; break; fi
  sleep 10
done
[ $ok -eq 1 ] || { log "FAIL: VM ssh not up"; exit 2; }
log "VM ssh OK: $($VSSH 'uname -r' 2>/dev/null)"

# ---------- S6: build rootfs in VM ----------
log "S6: populate rootfs (apk v3.24 main+community)"
$VSSH 'set -e
apk add --root=/newroot --initdb --arch=aarch64 --allow-untrusted \
  --repository https://dl-cdn.alpinelinux.org/alpine/v3.24/main --repository https://dl-cdn.alpinelinux.org/alpine/v3.24/community \
  alpine-base alpine-conf openssh openssh-server tcpdump aircrack-ng e2fsprogs build-base git libpcap-dev openssl-dev zlib-dev iw > /tmp/apk.log 2>&1 || { tail -5 /tmp/apk.log; exit 91; }
tail -2 /tmp/apk.log
echo ">>> apk done"' || { log "FAIL apk add (rc=$?)"; exit 3; }
log "hcxtools build in chroot"
git clone -q https://github.com/ZerBea/hcxtools $B/hcxtools 2>/dev/null || git clone -q --depth 1 https://github.com/ZerBea/hcxtools $B/hcxtools
tar -cf - -C $B/hcxtools . | $VSSH "mkdir -p /newroot/src/hcxtools && tar -xf - -C /newroot/src/hcxtools"
$VSSH 'set -e
chroot /newroot /bin/sh -c "cd /src/hcxtools && make -s -j2 2>&1 | tail -2; cp hcxpcapngtool /usr/local/bin/"
chroot /newroot /usr/local/bin/hcxpcapngtool -h 2>&1 | head -1
echo ">>> hcxtools done"' || { log "FAIL hcxtools"; exit 4; }
log "firmware + ssh + password into newroot"
$VSSH 'set -e
mkdir -p /newroot/lib/firmware
cp /lib/firmware/rt2870.bin /newroot/lib/firmware/ 2>/dev/null || true
mkdir -p /newroot/usr/lib/firmware
cp /lib/firmware/rt2870.bin /newroot/usr/lib/firmware/ 2>/dev/null || true
mkdir -p /newroot/root/.ssh
cp /root/.ssh/authorized_keys /newroot/root/.ssh/authorized_keys
echo "root:alpine123" | chroot /newroot /usr/sbin/chpasswd
chroot /newroot sh -c "ln -sf /usr/local/bin/hcxpcapngtool /usr/bin/hcxpcapngtool 2>/dev/null || true"
ln -sf /bin/busybox /newroot/sbin/init
# aircrack multicall symlinks (v3.24 package lacks airodump-ng/wpaclean/... entries)
ln -sf /usr/sbin/airodump-ng /newroot/usr/bin/airodump-ng
ln -sf /usr/sbin/aircrack-ng /newroot/usr/bin/aircrack-ng
ln -sf /usr/sbin/aireplay-ng /newroot/usr/bin/aireplay-ng
ln -sf /usr/sbin/airdecap-ng /newroot/usr/bin/airdecap-ng
ln -sf /usr/sbin/wpaclean /newroot/usr/bin/wpaclean 2>/dev/null || ln -sf /usr/sbin/aircrack-ng /newroot/usr/bin/wpaclean
ln -sf /usr/sbin/iw /newroot/usr/bin/iw
# sshd-only runlevel (mdev/networking/services hang OpenRC)
mkdir -p /newroot/etc/runlevels/default
ln -sf ../init.d/sshd /newroot/etc/runlevels/default/sshd
# silence getty respawn flood (no tty nodes in this kernel build)
sed -i "s/^tty/#tty/" /newroot/etc/inittab 2>/dev/null || true
touch /newroot/.build_done
echo ">>> rootfs populated"' || { log "FAIL finalize"; exit 5; }
$VSSH "sync; pkill -9 -f airod* 2>/dev/null; true" 
log "reboot VM for final config"
pkill -f qemu-system-aarch64; sleep 3
rm -f /tmp/vm_app_serial.log
nohup /opt/homebrew/bin/qemu-system-aarch64 -machine virt -cpu cortex-a72 -m 4096 -smp 4 \
  -drive file=/tmp/alpine-root.qcow2,format=qcow2 \
  -kernel /tmp/alpine-boot/boot/vmlinuz-lts -initrd /tmp/initramfs-custom -append "console=ttyAMA0" \
  -chardev file,id=s0,path=/tmp/vm_app_serial.log,append=on -serial chardev:s0 \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:2222-10.0.2.15:22 \
  -device virtio-net-pci,netdev=n0 \
  -device qemu-xhci,id=xhci -device usb-host,bus=xhci.0,vendorid=0x148f,productid=0x5572 \
  -display none -monitor unix:/tmp/vm_app_monitor.sock,server,nowait >/dev/null 2>&1 &
log "final qemu pid: $!"

log "wait for final VM (switch_root + firmware ~95s+)"
ok=0
for i in $(seq 1 60); do
  r=$($VSSH "iw dev 2>/dev/null | grep -c wlan0; dmesg 2>/dev/null | grep -c 'Firmware detected'" 2>/dev/null)
  a=$(echo "$r" | sed -n 1p); b=$(echo "$r" | sed -n 2p)
  if [ "${a:-0}" -ge 1 ] 2>/dev/null && [ "${b:-0}" -ge 1 ] 2>/dev/null; then ok=1; break; fi
  sleep 5
done
[ $ok -eq 1 ] || { log "WARN: wlan0/firmware not ready yet (may need more time)"; }
log "quick airodump sanity (10s)"
$VSSH 'ifconfig wlan0 down; iw dev wlan0 set type monitor; ifconfig wlan0 up; sleep 2
timeout 10 airodump-ng -w /tmp/sanity -c 1 wlan0 >/dev/null 2>&1
ls -la /tmp/sanity-*.cap 2>/dev/null | tail -2
echo ">>> REBUILD DONE"'
log "===== REBUILD END ====="
exit 0