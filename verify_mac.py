"""Verify Mac app: syntax + logic + APIs (dry run without tshark)."""
import sys, ast, threading, time
from pathlib import Path

APP = Path(r"C:\Users\crazydb911\Documents\deepseek\mac_wifi_cracker_v6.py")
source = APP.read_text()
print(f"=== Mac App Verification ===")
print(f"File: {APP} ({len(source)} bytes)")

# 1. Syntax check
try:
    tree = ast.parse(source)
    print(f"Syntax: OK ({len(tree.body)} top-level statements)")
except SyntaxError as e:
    print(f"Syntax ERROR: {e}")
    sys.exit(1)

# 2. Check imports
imports = []
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for a in node.names:
            imports.append(a.name)
    elif isinstance(node, ast.ImportFrom):
        imports.append(node.module)
print(f"Imports: {imports}")

required = ['os', 'sys', 'json', 'subprocess', 'threading', 'time', 're', 'requests', 'fastapi', 'uvicorn']
missing = [r for r in required if r not in imports]
print(f"Required imports: {'OK' if not missing else f'MISSING: {missing}'}")

# 3. Check API endpoints
endpoints = []
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and hasattr(dec.func, 'attr'):
                method = dec.func.attr
                if isinstance(dec.args[0], ast.Constant):
                    endpoints.append(f"{method.upper()} {dec.args[0].value}")
print(f"Endpoints: {endpoints}")

required_eps = ['/api/state', '/api/scan', '/api/capture', '/api/upload']
missing_eps = [e for e in required_eps if e not in endpoints]
print(f"Required endpoints: {'OK' if not missing_eps else f'MISSING: {missing_eps}'}")

# 4. Check key functions
functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
required_fns = ['scan_wifi', 'start_capture', 'upload_to_windows', 'poll_windows']
missing_fns = [f for f in required_fns if f not in functions]
print(f"Functions: {functions}")
print(f"Required functions: {'OK' if not missing_fns else f'MISSING: {missing_fns}'}")

# 5. Check HTML
html_start = source.find('<!DOCTYPE html>')
html_end = source.find('""")', html_start)
if html_start > 0:
    html = source[html_start:html_end]
    print(f"HTML: {len(html)} bytes")
    checks = ['Scan', 'Capture', 'Upload', 'Windows Status', 'Log', 'gpu-temp', 'temp-bar']
    for c in checks:
        status = 'OK' if c in html else 'MISSING'
        print(f"  {c}: {status}")

# 6. Check key logic
checks = {
    'tshark path': '/usr/local/bin/tshark' in source,
    'sudo password': 'SUDO_PASS' in source,
    'Windows URL': 'WINDOWS_URL' in source,
    'monitor mode': '-I' in source and 'IEEE802_11' in source,
    'upload to Windows': '/api/extract' in source,
    'poll Windows': '/api/state' in source,
    'EAPOL filter': 'eapol' in source,
}
print(f"\nLogic checks:")
for name, ok in checks.items():
    print(f"  {name}: {'OK' if ok else 'MISSING'}")

print()
print('=== MAC APP VERIFICATION COMPLETE ===')
