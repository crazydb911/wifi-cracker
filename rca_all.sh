#!/bin/sh
for ch in 1 3 4 6 8 10 11; do
  timeout 25 hcxdumptool -i wlan0 -c $ch"a" --rcascan=active --rds=2 --rdt >/tmp/rca_$ch.txt 2>&1
  echo "=== ch$ch ==="
  tr '\r' '\n' < /tmp/rca_$ch.txt | grep -v '^CHA' | grep -v '^---' | awk -F'|' '{gsub(/ /,"",$3); if ($3 != "") print $2, $3, $4, $6}' | sort -u | head -8
done
