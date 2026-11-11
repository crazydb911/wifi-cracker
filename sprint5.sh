#!/bin/sh
# Sprint5: ZERO interface touching. Only reg domain + channel. Measures survival too.
V="sudo ssh -i /Users/tongbao/.ssh/vm_tongbao -p 2222 -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=6 root@127.0.0.1"
G="chroot /newroot"
R=/tmp/s5.txt
scan() {  # $1=chan $2=label
  echo "--- $2 ch$1 $(date +%H:%M:%S)" >> $R
  $V "$G timeout 25 hcxdumptool -i wlan0 -c $1 --rcascan=active 2>&1 | grep -aE 'BEACONs|PROBERESPONSEs|PROBEREQUESTs|Packet\(s\)|ERROR|injection|TX ' | tail -6" >> $R 2>&1
}
echo "SPRINT5 armed $(date +%H:%M:%S)" > $R
phy=""
i=0
while [ $i -lt 600 ]; do
  i=$((i+1))
  phy=$($V 'ls /sys/class/ieee80211/ 2>/dev/null' 2>/dev/null)
  [ -n "$phy" ] && break
  sleep 2
done
if [ -z "$phy" ]; then echo "NO_PHY_20MIN $(date +%H:%M:%S)" >> $R; exit 0; fi
echo "PHY_UP $phy $(date +%H:%M:%S)" >> $R
# reg domain only -- NO ifconfig, NO set type
$V "$G /usr/sbin/iw reg set TW; sleep 1; $G /usr/sbin/iw reg get | sed -n 2p; $G /usr/sbin/iw dev wlan0 info 2>&1 | grep -E 'type|channel|txpower'" >> $R 2>&1
scan 1a  BASELINE_2.4G
scan 36b ACTIVE_5G_try1
scan 36b ACTIVE_5G_try2
scan 1a  POST_2.4G_survival
echo "SPRINT5_DONE $(date +%H:%M:%S)" >> $R
$V "$G dmesg | tail -5" >> $R 2>&1
