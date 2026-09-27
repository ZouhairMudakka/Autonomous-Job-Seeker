"""Small shared helpers for local, atomic storage operations."""

from contextlib import contextmanager
import os
from pathlib import Path
import re
import tempfile
import threading


_locks = {}
_locks_guard = threading.Lock()


def file_lock(path):
    """Serialize file transactions across instances in this process."""
    key = str(Path(path).resolve())
    with _locks_guard:
        return _locks.setdefault(key, threading.RLock())


def safe_child(directory, filename):
    """Reject path components, Windows device names and escaping symlinks."""
    if (not isinstance(filename, str) or not filename or
            filename in {'.', '..'} or filename[-1:] in {' ', '.'} or
            re.search(r'[<>:"/\\|?*\x00-\x1f]', filename) or
            re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', filename, re.I)):
        raise ValueError('Expected a plain filename without path components')
    root = Path(directory).resolve()
    path = root / filename
    if path.resolve().parent != root:
        raise ValueError('Storage path must remain inside its configured directory')
    return path


@contextmanager
def atomic_text_writer(path, *, newline=None):
    """Replace a file only after its complete UTF-8 contents are written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', newline=newline, dir=path.parent,
            prefix=f'.{path.name}.', suffix='.tmp', delete=False,
        ) as stream:
            temporary = Path(stream.name)
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
