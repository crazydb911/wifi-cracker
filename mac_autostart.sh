#!/bin/sh
# LaunchDaemon wrapper: wait for GUI console session, then exec the app as user 501.
# Must exec (not background) or launchd kills the child.
export HOME=/Users/tongbao
while true; do
  cu=$(stat -f%Su /dev/console 2>/dev/null)
  if [ "$cu" = "tongbao" ]; then break; fi
  sleep 5
done
sleep 8
exec launchctl asuser 501 "/Users/tongbao/Desktop/WiFi破解台.app/Contents/MacOS/MacCapture"
