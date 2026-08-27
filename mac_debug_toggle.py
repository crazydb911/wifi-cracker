"""Test WiFi toggle methods + check for EAPOL.

Strategy: start tshark capture, then try different toggle methods,
and check the capture for EAPOL after each.
"""
import paramiko, time, subprocess

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=10)

def ssh(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err

def run_sudo(cmd, timeout=15):
    """Run command with sudo on Mac."""
    out, err = ssh(f"echo '{SUDO_PASS}' | sudo -S {cmd}", timeout=timeout)
    return out, err

# First: check if Mac is currently connected to 32H9F_5G
print("=== Current WiFi state ===")
out, _ = ssh("networksetup -getairportpower en0")
print(out.strip())
out, _ = ssh("networksetup -getairportnetwork en0")
print(f"Connected to: {out.strip()}")
out, _ = ssh("ifconfig en0 | grep 'ether'")
print(f"MAC: {out.strip()}")

# Check if Mac has an active session (lease)
out, _ = ssh("ipconfig getpacket en0 2>&1 | head -5")
print(f"\nDHCP lease:\n{out}")

# === Method 1: Disconnect via airport -I en0 --setbssid, then reconnect ===
print("\n=== Method 1: airport -z + setairportpower off/on (15s gap) ===")
cap = "/tmp/toggle_test1.pcap"
# Start capture in background
run_sudo(f"/usr/local/bin/tshark -i en0 -I -y IEEE802_11 -c 5000 -w {cap} &", timeout=5)
time.sleep(3)
# Toggle
print("  Off...")
ssh("networksetup -setairportpower en0 off")
time.sleep(15)
print("  On...")
ssh("networksetup -setairportpower en0 on")
time.sleep(25)
# Stop capture
ssh("pkill -f 'tshark.*toggle_test1'")
time.sleep(2)
# Count EAPOL
out, _ = ssh(f"echo '{SUDO_PASS}' | sudo -S cp {cap} ~/toggle_test1.pcap && echo '{SUDO_PASS}' | sudo -S chmod 644 ~/toggle_test1.pcap && /usr/local/bin/tshark -r ~/toggle_test1.pcap -Y eapol -T fields -e frame.number 2>&1 | wc -l")
print(f"  EAPOL frames: {out.strip()}")
out, _ = ssh(f"/usr/local/bin/tshark -r ~/toggle_test1.pcap -T fields -e frame.protocols 2>&1 | sort | uniq -c | sort -rn | head -5")
print(f"  Protocols:\n{out}")

# Check if Mac is back online
out, _ = ssh("networksetup -getairportnetwork en0")
print(f"  Now connected to: {out.strip()}")

client.close()
print("\nDone.")
