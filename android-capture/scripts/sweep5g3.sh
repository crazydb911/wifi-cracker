#!/system/bin/sh
reset_if() {
  pkill -9 tcpdump 2>/dev/null
  ip link set wlan0 down 2>/dev/null; sleep 1
  echo 0 > /sys/module/wlan/parameters/con_mode 2>/dev/null; sleep 1
  echo 4 > /sys/module/wlan/parameters/con_mode 2>/dev/null; sleep 2
  ip link set wlan0 up 2>/dev/null; sleep 2
}
sw() {
  ch=$1; freq=$2
  reset_if
  iw dev wlan0 set freq $freq HT20 2>/dev/null
  sleep 1
  rm -f /data/local/tmp/s5_$ch.pcap
  timeout 8 tcpdump -i wlan0 -w /data/local/tmp/s5_$ch.pcap -s 0 >/dev/null 2>&1 &
  TPID=$!
  sleep 1
  /data/local/tmp/probe wlan0 bc3e0701dc92 bc3e0701dc92 32H10F 12 120 2>/dev/null
  /data/local/tmp/probe wlan0 bc3e0701dc92 ffffffffffff 32H10F 12 120 2>/dev/null
  /data/local/tmp/probe wlan0 bc3e0701dc98 bc3e0701dc98 32H10F 6 150 2>/dev/null
  wait $TPID 2>/dev/null
  echo "ch$ch($freq) = $(wc -c < /data/local/tmp/s5_$ch.pcap 2>/dev/null) bytes"
}
for pair in "36 5180" "40 5200" "44 5220" "48 5240" "52 5280" "56 5300" "60 5320" "64 5340" "149 5745" "153 5765" "157 5785" "161 5805" "165 5825"; do
  set -- $pair; sw $1 $2
done
echo SWEEP5G3_DONE
