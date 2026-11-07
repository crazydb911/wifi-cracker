#!/bin/sh
# Manual QEMU boot with the capture adapter (mirrors the app's command).
sudo /opt/homebrew/bin/qemu-system-aarch64 \
  -machine virt -cpu cortex-a72 -m 1024 -smp 2 \
  -drive file=/Users/tongbao/vmbuild/alpine-root.qcow2,format=qcow2 \
  -kernel /Users/tongbao/vmbuild/alpine-boot/boot/vmlinuz-lts \
  -initrd /Users/tongbao/vmbuild/vmbuild/runner-initrd \
  -append "console=ttyAMA0 cfg80211.ieee80211_regdom=TW" \
  -chardev file,id=s0,path=/tmp/vm_manual_serial.log,append=on -serial chardev:s0 \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:2222-10.0.2.15:22 \
  -device virtio-net-pci,netdev=n0 \
  -device qemu-xhci,id=xhci \
  -device usb-host,bus=xhci.0,vendorid=0x148f,productid=0x5572,id=wifiBoot \
  -display none -monitor unix:/tmp/vm_manual_monitor.sock,server,nowait
