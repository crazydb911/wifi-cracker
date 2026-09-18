#!/bin/bash
# mac_handsoff.sh — 讓 Mac 重啟後免手動解鎖（FileVault off + auto-login）
# 需在 Mac 有網路、可 sudo 時執行一次
set -u
SUDO="sudo -S -p ''"
PW=240628
LOG=/tmp/mac_handsoff.log
exec > >(tee -a $LOG) 2>&1

echo "[$(date '+%H:%M:%S')] === hands-off setup start ==="

# 1) FileVault: check & disable
echo "--- FileVault status ---"
echo "$PW" | $SUDO fdesetstatus 2>&1 | head -4
if echo "$PW" | $SUDO fdesetstatus 2>&1 | grep -q "being updated\|On"; then
  echo "--- disabling FileVault (takes effect next boot) ---"
  echo "$PW" | $SUDO fdesetoff 2>&1 | head -3
else
  echo "FileVault already off or n/a"
fi

# 2) auto-login (best effort; modern macOS may ignore without stored hash)
echo "--- auto-login ---"
echo "$PW" | $SUDO defaults write /Library/Preferences/com.apple.loginwindow AutoLoginUser -int 3 2>&1
echo "$PW" | $SUDO defaults write /Library/Preferences/com.apple.loginwindow ENABLE_AUTO_LOGOUT -int 0 2>&1
/usr/bin/defaults read /Library/Preferences/com.apple.loginwindow AutoLoginUser 2>&1

# 3) sshd on wake/boot
echo "$PW" | $SUDO systemsetup -setremotelogin on 2>&1 | head -2

# 4) verify vm artifacts present
B=$HOME/vmbuild
echo "--- artifacts ---"
ls -la $B/vmbuild/boot/vmlinuz-lts $B/vmbuild/runner-initrd $B/alpine-root.qcow2 2>&1

echo "[$(date '+%H:%M:%S')] === hands-off setup done ==="