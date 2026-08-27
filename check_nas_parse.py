import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.115', username='crazydb911', 
               key_filename='C:/Users/crazydb911/.ssh/codex_nas_ed25519', timeout=10)

# Check the NAS parse script
stdin, stdout, stderr = client.exec_command('cat /volume1/docker1/codex/workspace/ai-shared/AI-Handoff/_parse.py')
print("NAS _parse.py:")
print(stdout.read().decode())

client.close()
