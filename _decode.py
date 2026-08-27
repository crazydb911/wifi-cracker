import base64
pairs = [
 (r"C:\Users\CRAZYD~1\AppData\Local\Temp\32h9f_eapol.b64", r"C:\Users\crazydb911\Documents\deepseek\32h9f_eapol.pcapng"),
 (r"C:\Users\CRAZYD~1\AppData\Local\Temp\readme.b64", r"C:\Users\crazydb911\Documents\deepseek\netdiag_README.md"),
 (r"C:\Users\CRAZYD~1\AppData\Local\Temp\parse_cap.b64", r"C:\Users\crazydb911\Documents\deepseek\netdiag_parse_cap.py"),
]
for src, dst in pairs:
    raw = open(src, 'rb').read().strip()
    data = base64.b64decode(raw)
    open(dst, 'wb').write(data)
    print(dst, len(data), "bytes")
