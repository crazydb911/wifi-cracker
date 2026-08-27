"""Mac Control API - remote control via HTTP (port 8765).
Add these endpoints to mac_wifi_cracker_v6.py.
"""

# Add imports at top
import shlex

# Add control state
CONTROL_STATE = {
    "cmds": [],  # command history
    "last_output": None,
    "running": False,
}

def run_control(cmd, timeout=30):
    """Run a command on Mac via SSH (or direct if running locally)."""
    try:
        # Use subprocess (local execution)
        p = subprocess.run(
            shlex.split(cmd) if " " in cmd else [cmd],
            capture_output=True, text=True, timeout=timeout
        )
        output = p.stdout + p.stderr
        return {"ok": True, "exit_code": p.returncode, "output": output}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout ({timeout}s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def run_sudo_control(cmd, timeout=30):
    """Run a command with sudo."""
    try:
        p = subprocess.run(
            ["sudo", "-S"] + shlex.split(cmd),
            input=(SUDO_PASS + "\n").encode(),
            capture_output=True, text=True, timeout=timeout
        )
        output = p.stdout + p.stderr
        return {"ok": True, "exit_code": p.returncode, "output": output}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout ({timeout}s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# Add endpoints
@app.get("/api/control")
async def api_control_status():
    """Get control status."""
    return JSONResponse({
        "running": CONTROL_STATE["running"],
        "last_output": CONTROL_STATE["last_output"],
        "history": CONTROL_STATE["cmds"][-20:]
    })

@app.post("/api/control/run")
async def api_control_run(cmd: str, sudo: bool = False, timeout: int = 30):
    """Run a command on Mac."""
    CONTROL_STATE["running"] = True
    CONTROL_STATE["cmds"].append(f"$ {cmd}")
    
    if sudo:
        result = run_sudo_control(cmd, timeout)
    else:
        result = run_control(cmd, timeout)
    
    CONTROL_STATE["last_output"] = result
    CONTROL_STATE["running"] = False
    
    # Log
    log(f"Control: {cmd} -> {result.get('exit_code', 'error')}")
    
    return JSONResponse(result)

@app.post("/api/control/ssh")
async def api_control_ssh(cmd: str, timeout: int = 30):
    """Run command via SSH (for remote control)."""
    try:
        import paramiko
        key = paramiko.Ed25519Key.from_private_key_file("/Users/crazydb911/.ssh/opremote_ed25519")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect("192.168.1.102", port=22, username="crazydb911", pkey=key, timeout=15)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        output = stdout.read().decode() + stderr.read().decode()
        client.close()
        return JSONResponse({"ok": True, "output": output})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})

@app.get("/api/control/files")
async def api_control_files(path: str = "/Users/crazydb911"):
    """List files."""
    try:
        result = run_control(f"ls -la {path}")
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})

@app.get("/api/control/tail")
async def api_control_tail(file: str, lines: int = 20):
    """Tail a file."""
    try:
        result = run_control(f"tail -{lines} {file}")
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})
