import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.102', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/opremote_ed25519', timeout=10)

# Install scapy
stdin, stdout, stderr = client.exec_command('pip3 install scapy')
print('pip3 install scapy:')
print(stdout.read().decode())
print(stderr.read().decode())

# Verify
stdin, stdout, stderr = client.exec_command('python3 -c "import scapy; print(scapy.__version__)"')
print('Scapy:', stdout.read().decode().strip())

client.close()
