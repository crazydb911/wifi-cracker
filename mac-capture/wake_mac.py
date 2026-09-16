#!/usr/bin/env python3
# Wake the Mac (tongbao@192.168.1.125) via Wake-on-LAN magic packet.
#
# The Mac is powered ON but may be asleep. Note on WoL MAC:
#   * While the built-in Wi-Fi (en0) is the active NIC, target en0's MAC.
#   * After the built-in is DISABLED (see disable_builtin_wifi.sh), the Mac runs
#     on the USB card (DWA-160) — WoL then must target the DWA-160's burned-in
#     MAC (pass it as the first arg). USB Wi-Fi WoL support varies by driver.
#
# Usage: python wake_mac.py [mac] [host]
import socket, sys
mac = (sys.argv[1] if len(sys.argv) > 1 else "74:a6-cd-bd-43:f2").replace(":", "").replace("-", "")
host = sys.argv[2] if len(sys.argv) > 2 else "192.168.1.125"
pkt = b"\xff" * 6 + bytes.fromhex(mac * 16)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
for _ in range(10):
    for d in (host, "192.168.1.255", "255.255.255.255"):
        s.sendto(pkt, (d, 9))
s.close()
print(f"WoL sent to {mac} (host {host}); wait ~25s then: ssh -i ~/.ssh/opremote_ed25519 tongbao@{host}")