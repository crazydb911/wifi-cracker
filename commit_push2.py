"""Commit + push all changes to GitHub (fix quoting)."""
import subprocess

# Git add + commit + push
print("Git add...")
r = subprocess.run("git add -A", capture_output=True, text=True, cwd=r"C:\Users\crazydb911\Documents\deepseek")
print(f"  {r.stderr.strip()}")

print("\nGit commit...")
msg = "Mac app v8: control API + security detect + capture improvements"
r = subprocess.run(
    ["git", "commit", "-m", msg],
    capture_output=True, text=True, cwd=r"C:\Users\crazydb911\Documents\deepseek"
)
print(f"  {r.stdout.strip()}")
print(f"  {r.stderr.strip()}")

print("\nGit push...")
r = subprocess.run("git push origin main", capture_output=True, text=True, cwd=r"C:\Users\crazydb911\Documents\deepseek")
print(f"  {r.stdout.strip()}")
print(f"  {r.stderr.strip()}")
