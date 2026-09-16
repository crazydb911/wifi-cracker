#!/bin/bash
# ---------------------------------------------------------------------------
# Disable the Mac's built-in Wi-Fi (Apple AirPort, en0) so the Mac's network
# runs ONLY over the USB Wi-Fi card (D-Link DWA-160, RTL8811AU).
#
# Why:
#  * The built-in Apple Wi-Fi uses a per-network RANDOMIZED MAC and its
#    WoL/magic-packet wake is flaky; it also occupies the 2.4G band.
#  * Running the Mac on the USB card only makes the DWA-160 the single,
#    deterministic network + capture device (and the sole SSH path).
#
# Usage:
#   ./disable_builtin_wifi.sh off      # disable built-in (default)
#   ./disable_builtin_wifi.sh on       # re-enable built-in
# Env:
#   SUDO_PW   sudo password (default 240628)
#   BUILTIN   built-in AirPort interface name (default en0)
#   USBIFACE  USB Wi-Fi card interface name (default en1, auto-detected)
# ---------------------------------------------------------------------------
set -u
ACTION="${1:-off}"
export SUDO_PW="${SUDO_PW:-240628}"
BUILTIN="${BUILTIN:-en0}"
sudo() { command sudo -S "$@" <<<"$SUDO_PW"; }

# Find the USB Wi-Fi card interface: a non-built-in enN whose MAC is NOT the
# Apple AirPort OUI (built-in is 74:a6:cd:bd:43:f2). We look for enN that has
# an inet address and is active, excluding $BUILTIN.
detect_usb() {
  local iface
  for iface in $(ifconfig -l); do
    case "$iface" in en*) ;; *) continue ;; esac
    [ "$iface" = "$BUILTIN" ] && continue
    if ifconfig "$iface" 2>/dev/null | grep -q "status: active"; then
      echo "$iface"; return 0
    fi
  done
  return 1
}

echo "=== interfaces BEFORE ==="
ifconfig | awk '/^[a-z0-9]+:/{iface=$1;st=""} /status:/{st=$3} /inet /{print iface, $2, $3, "st=" st}' | grep -v "^lo0" || true
echo

if [ "$ACTION" = "off" ]; then
  USB=$(detect_usb || echo "NONE")
  if [ "$USB" = "NONE" ]; then
    echo "WARNING: no active non-built-in Wi-Fi interface found before disabling $BUILTIN."
    echo "Disabling $BUILTIN now will likely DROP all network (incl. SSH). Continuing in 5s... (Ctrl-C to abort)"
    sleep 5
  else
    echo "USB Wi-Fi card (DWA-160) active on: $USB  ->  safe to disable built-in $BUILTIN"
  fi
  echo "=== DISABLING built-in Wi-Fi ($BUILTIN) ==="
  sudo networksetup -setairportpower "$BUILTIN" off
  sudo ifconfig "$BUILTIN" down 2>/dev/null || true
else
  echo "=== ENABLING built-in Wi-Fi ($BUILTIN) ==="
  sudo networksetup -setairportpower "$BUILTIN" on
  sudo ifconfig "$BUILTIN" up 2>/dev/null || true
fi

sleep 2
echo
echo "=== interfaces AFTER ==="
ifconfig | awk '/^[a-z0-9]+:/{iface=$1;st=""} /status:/{st=$3} /inet /{print iface, $2, $3, "st=" st}' | grep -v "^lo0" || true
echo
echo "Mac now runs over the USB Wi-Fi card (DWA-160) only. If the Mac's IP changed,"
echo "re-detect it before SSHing (ping scan 192.168.1.x or check the router's DHCP table)."