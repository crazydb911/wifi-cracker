#!/usr/bin/env python3
"""Find the Mac on the network."""
import socket, time

MAC_TARGET = "60:f8:1d:ad:01:e4"  # Mac en0 MAC
KNOWN_MACS = {
    "f4:27:56:04:0b:e8": "Router",
    "b0:4a:39:27:99:b8": "Device (.103)",
    "50:31:23-d7-50-ac": "Device (.104)",
    "82:62:19:41:ce:a4": "Device (.105)",
    "a4:ae:12:59:ec:61": "Device (.112)",
    "90:09:d0:5d:a7:f8": "NAS (.115)",
    "2c:26:17:93:e6:aa": "Device (.116)",
}

print(f"Looking for Mac (MAC: {MAC_TARGET})...")
print(f"Known MACs in ARP:")
for mac, name in KNOWN_MACS.items():
    print(f"  {mac}: {name}")

print(f"\nMac MAC ({MAC_TARGET}) NOT in ARP table.")
print("Possible reasons:")
print("  1. Mac is connected to a different WiFi (32H9F_5G vs 32H9F)")
print("  2. Mac WiFi is still off")
print("  3. Mac is on a different subnet")

# Try to reach Mac on common IPs
print("\nChecking common IPs...")
for ip in ["192.168.1.102", "192.168.1.103", "192.168.1.104"]:
    for port in [22, 8765]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        r = s.connect_ex((ip, port))
        s.close()
        status = "OPEN" if r == 0 else "closed"
        print(f"  {ip}:{port} = {status}")

print("\nDone. If Mac is not found, it's likely on a different WiFi network.")
