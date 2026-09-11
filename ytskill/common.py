from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import signal
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class Problem(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def video_id(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        raise Problem("invalid_url", "Supply a YouTube video URL or its 11-character ID.")
    if host == "youtu.be":
        candidate = parsed.path.strip("/")
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        parts = parsed.path.strip("/").split("/")
        if parts == ["watch"]:
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        elif len(parts) == 2 and parts[0] in {"shorts", "embed", "live"}:
            candidate = parts[1]
        else:
            candidate = ""
    else:
        candidate = ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
        raise Problem("invalid_url", "Only a single YouTube video is supported; playlist/channel URLs are not.")
    return candidate


def canonical_url(identity: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id(identity)}"


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise Problem("invalid_json", f"Cannot read JSON from {path.name}: {type(exc).__name__}") from exc


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def confined(root: Path, relative: str, *, exists=False) -> Path:
    root = root.resolve()
    target = (root / relative).resolve()
    if target == root or not target.is_relative_to(root):
        raise Problem("unsafe_path", "File path must stay inside its designated directory.")
    if exists and not target.is_file():
        raise Problem("missing_file", f"Missing file: {relative}")
    return target


def finite(value, label="timestamp") -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise Problem("invalid_timestamp", f"{label} must be a finite non-negative number.") from exc
    if not math.isfinite(result) or result < 0:
        raise Problem("invalid_timestamp", f"{label} must be a finite non-negative number.")
    return result


def tokens(text: str) -> int:
    # An estimate, not a model tokenizer; conservative on non-whitespace scripts.
    non_ascii = sum(ord(c) > 127 for c in text)
    return max(1, math.ceil(max(len(text) / 4, len(text.split()) / .75, non_ascii / 1.5)))


def clock(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{total // 60 % 60:02d}:{total % 60:02d}"


def stop_windows_tree(pid: int):
    # Toolhelp works without taskkill's service/RPC access, which can be denied
    # in otherwise capable Windows agent sandboxes. Only our PID's descendants
    # are selected; never terminate unrelated processes by executable name.
    import ctypes
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD), ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD), ("name", wintypes.WCHAR * 260)]
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    api.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ["Process32FirstW", "Process32NextW"]:
        getattr(api, name).argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        getattr(api, name).restype = wintypes.BOOL
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = api.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        return
    children = {}
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(entry)
        found = api.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            children.setdefault(entry.parent, []).append(entry.pid)
            found = api.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        api.CloseHandle(snapshot)
    order, seen = [pid], {pid}
    for parent in order:
        for child in children.get(parent, []):
            if child not in seen:
                order.append(child)
                seen.add(child)
    for target in reversed(order):
        handle = api.OpenProcess(1, False, target)
        if handle:
            try:
                api.TerminateProcess(handle, 1)
            finally:
                api.CloseHandle(handle)


def execute(argv: list[str], *, timeout=120, env=None) -> subprocess.CompletedProcess:
    try:
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", env=env, start_new_session=os.name != "nt", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            # yt-dlp may own an FFmpeg child. Kill only our utility's process
            # tree, so a timed-out section cannot keep downloading in hiding.
            if os.name == "nt":
                stop_windows_tree(process.pid)
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.kill()
            process.communicate()
            raise Problem("timeout", "Utility timed out; its child processes were stopped and completed checkpoints retained.") from exc
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    except OSError as exc:
        raise Problem("missing_dependency", f"Cannot run {Path(argv[0]).name}: {type(exc).__name__}") from exc
