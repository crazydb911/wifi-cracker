import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Check for airport
stdin, stdout, stderr = client.exec_command('which airport || echo "NOT FOUND"')
print("airport:", stdout.read().decode().strip())

# Check for hcxdumptool
stdin, stdout, stderr = client.exec_command('which hcxdumptool || echo "NOT FOUND"')
print("hcxdumptool:", stdout.read().decode().strip())

# Check for airodump-ng
stdin, stdout, stderr = client.exec_command('which airodump-ng || echo "NOT FOUND"')
print("airodump-ng:", stdout.read().decode().strip())

# Check for tshark
stdin, stdout, stderr = client.exec_command('which tshark || echo "NOT FOUND"')
print("tshark:", stdout.read().decode().strip())

# Check for hcxpcapngtool
stdin, stdout, stderr = client.exec_command('which hcxpcapngtool || echo "NOT FOUND"')
print("hcxpcapngtool:", stdout.read().decode().strip())

# Check for hashcat
stdin, stdout, stderr = client.exec_command('which hashcat || echo "NOT FOUND"')
print("hashcat:", stdout.read().decode().strip())

client.close()
