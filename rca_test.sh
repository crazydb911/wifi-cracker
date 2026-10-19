#!/bin/sh
ifconfig wlan0 down
iw dev wlan0 set type monitor
ifconfig wlan0 up
timeout 50 hcxdumptool -i wlan0 -c 6a --rcascan=active --rds=2 --rdt >/tmp/rca.txt 2>&1
echo LINES=$(wc -l < /tmp/rca.txt)
tr '\r' '\n' < /tmp/rca.txt | grep -v '^ *$' | tail -35
