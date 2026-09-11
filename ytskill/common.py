from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
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


def execute(argv: list[str], *, timeout=120, env=None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired as exc:
        raise Problem("timeout", "Utility timed out; completed checkpoints are retained.") from exc
    except OSError as exc:
        raise Problem("missing_dependency", f"Cannot run {Path(argv[0]).name}: {type(exc).__name__}") from exc
