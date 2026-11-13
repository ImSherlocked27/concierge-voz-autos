"""Run the official CLI with local dotenv credentials without printing them."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

from dotenv import load_dotenv


def main():
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    executable = shutil.which("elevenlabs")
    if executable:
        command = [executable]
    else:
        executable = shutil.which("npx")
        if not executable:
            raise SystemExit("Install Node.js and the official @elevenlabs/cli first")
        command = [executable, "-y", "@elevenlabs/cli@1.11.0"]
    raise SystemExit(subprocess.run([*command, *sys.argv[1:]], cwd=root, env=os.environ.copy()).returncode)


if __name__ == "__main__":
    main()
