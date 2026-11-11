"""Windows launcher using Python directly; no PowerShell policy changes."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    python = root / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")], check=True)
    check = subprocess.run(
        [str(python), "-c", "import fastapi,uvicorn,httpx,yaml,dotenv"],
        capture_output=True,
    )
    if check.returncode:
        subprocess.run([str(python), "-m", "pip", "install", "-r", "requirements-lock.txt"], check=True)
    return subprocess.call([str(python), "run.py", "--prompt-key", "--open-browser"])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Unable to start CarePlan: {exc}")
        raise SystemExit(1)
