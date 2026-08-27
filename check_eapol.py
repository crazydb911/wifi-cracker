"""Check what those 2 EAPOL frames are."""
import subprocess

pcap = r"C:\Users\crazydb911\Documents\deepseek\sudo_cap.pcap"

# Get EAPOL frame details
cmd = [r"C:\Program Files\Wireshark\tshark.exe" if __import__('os').path.exists(r"C:\Program Files\Wireshark\tshark.exe") else "tshark",
       "-r", pcap, "-Y", "eapol", "-V", "eapol"]
print("=== EAPOL frame details ===")
try:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    print(r.stdout[:2000])
    if r.stderr:
        print(f"STDERR: {r.stderr[:500]}")
except Exception as e:
    print(f"Error: {e}")
    # Try with full path
    import glob
    tsharks = glob.glob(r"C:\Program Files*\Wireshark\tshark.exe")
    print(f"Available tsharks: {tsharks}")
    if tsharks:
        r = subprocess.run([tsharks[0], "-r", pcap, "-Y", "eapol", "-V", "eapol"], capture_output=True, text=True, timeout=30)
        print(r.stdout[:2000])
