#!/system/bin/sh
reset_if() {
  pkill -9 tcpdump 2>/dev/null
  ip link set wlan0 down 2>/dev/null; sleep 1
  echo 0 > /sys/module/wlan/parameters/con_mode 2>/dev/null; sleep 1
  echo 4 > /sys/module/wlan/parameters/con_mode 2>/dev/null; sleep 2
  ip link set wlan0 up 2>/dev/null; sleep 3
}
sw() {
  ch=$1; freq=$2
  reset_if
  iw dev wlan0 set freq $freq 2>/dev/null
  sleep 1
  rm -f /data/local/tmp/tg_$ch.pcap
  timeout 15 tcpdump -i wlan0 -w /data/local/tmp/tg_$ch.pcap -s 0 >/dev/null 2>&1
  echo "ch$ch($freq) = $(wc -c < /data/local/tmp/tg_$ch.pcap 2>/dev/null) bytes"
}
sw 1 2412
sw 6 2437
sw 11 2462
echo SWEEP2G_DONE
