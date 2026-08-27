"""Check EAPOL frames (paramiko SSH)."""
import paramiko

HOST = "192.168.1.102"
USER = "crazydb911"
KEY = r"C:\Users\crazydb911\.ssh\opremote_ed25519"
SUDO_PASS = " "

key = paramiko.Ed25519Key.from_private_key_file(KEY)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, pkey=key, timeout=15)

def ssh(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Check EAPOL in most recent capture
out, err = ssh("echo ' ' | sudo -S /usr/local/bin/tshark -r /Users/crazydb911/cap_f8345a8c1f9f_1787845952.pcap -Y 'eapol' -T fields -e frame.number -e eapol.type -e wlan.sa -e wlan.da 2>&1", timeout=30)
print("EAPOL frames in most recent capture:")
print(out if out else err)

client.close()
print("\nDone!")
