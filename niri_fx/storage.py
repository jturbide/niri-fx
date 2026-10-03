"""Small filesystem primitives shared by setup, registries and Studio preferences.

Callers own symlink policy, conflict checks and locks. Atomic replacement prevents
partial file contents; it does not turn a multi-file setup into one transaction.
"""

import hashlib
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


def read_bytes(path):
    """Distinguish an absent file (None) from an existing empty file (b'')."""
    return path.read_bytes() if path.exists() else None


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


@contextmanager
def staged_write(path, data, mode=0o600):
    """Yield a flushed sibling file for a caller-controlled atomic replacement.

    Staging in the destination directory keeps rename on one filesystem. The
    registry writer uses the gap before replacement to recheck the old contents
    and save its backup. Both successful rename and exceptions clean up the stage.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".nirifx-", delete=False
        ) as output:
            temporary = Path(output.name)
            os.fchmod(output.fileno(), mode)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        yield temporary
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_write(path, data, mode=0o600):
    """Replace bytes, or remove a file for None. Callers check expected contents."""
    if data is None:
        path.unlink(missing_ok=True)
        return
    with staged_write(path, data, mode) as temporary:
        os.replace(temporary, path)
