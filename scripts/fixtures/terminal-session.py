"""Run the real CLI twice in a test PTY; the outer harness supplies all input."""

import os
import subprocess
import sys
import time
from pathlib import Path

root = Path(os.environ["NIRIFX_TEST_DIRECTORY"])
executable = os.environ.get("NIRIFX_TEST_EXECUTABLE")
command = [executable] if executable else [sys.executable, "-m", "niri_fx"]
for index in (1, 2):
    print("\n$ niri-fx", flush=True)
    subprocess.run(command, cwd=root if executable else None, check=True)
    (root / f"completed-{index}").touch()
    time.sleep(1)
