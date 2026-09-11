from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from . import retrieval, runs, validation
from .common import Problem, atomic_json, read_json


def parser():
    root = argparse.ArgumentParser(description="Free video evidence extraction. The host agent synthesizes the skill.")
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check available lightweight utilities; never install models.")
    bootstrap = sub.add_parser("bootstrap", help="Set up free utilities in an explicitly chosen isolated environment.")
    bootstrap.add_argument("--env-dir", type=Path, required=True)
    bootstrap.add_argument("--visual", action="store_true")
    prep = sub.add_parser("prepare", help="Retrieve or import one completed video's timed evidence.")
    prep.add_argument("url")
    prep.add_argument("--work-dir", type=Path, required=True)
    prep.add_argument("--transcript", type=Path)
    prep.add_argument("--metadata", type=Path)
    prep.add_argument("--language")
    prep.add_argument("--unit-tokens", type=int, default=3000)
    prep.add_argument("--transcription-method")
    prep.add_argument("--consent-run", type=Path)
    for name in ["status", "resume", "read", "record", "review", "consent", "frames", "audio", "map", "validate"]:
        command = sub.add_parser(name)
        command.add_argument("--run-dir", type=Path, required=True)
        if name in {"status", "resume"}:
            command.add_argument("--details", action="store_true")
        elif name == "read":
            command.add_argument("--unit")
            command.add_argument("--start", type=float)
            command.add_argument("--end", type=float)
        elif name in {"record", "review", "map"}:
            command.add_argument("--file", type=Path, required=True)
        elif name == "consent":
            command.add_argument("--choice", choices=["granted", "declined"], required=True)
        elif name == "frames":
            command.add_argument("--media", type=Path)
            command.add_argument("--overview", action="store_true")
            command.add_argument("--start", type=float, default=0)
            command.add_argument("--end", type=float)
            command.add_argument("--every", type=float, default=5)
            command.add_argument("--detail", action="store_true")
            command.add_argument("--no-scenes", action="store_true")
        elif name == "validate":
            command.add_argument("--output", type=Path, required=True)
            command.add_argument("--accept-findings", type=Path)
    return root


def bootstrap(directory: Path, visual=False):
    import venv
    directory = directory.resolve()
    if directory.exists() and any(directory.iterdir()) and not (directory / "pyvenv.cfg").is_file():
        raise Problem("unsafe_environment", "Environment directory is not empty and is not a Python venv.")
    if not (directory / "pyvenv.cfg").exists():
        venv.EnvBuilder(with_pip=True).create(directory)
    executable = directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    requirements = ['yt-dlp[default]>=2026.8.19', 'youtube-transcript-api>=1.2.4,<2']
    if visual:
        requirements += ["pillow>=10.1", "imageio-ffmpeg>=0.6,<1"]
    # pip progress belongs on stderr; stdout remains a machine-readable envelope.
    result = subprocess.run([str(executable), "-m", "pip", "install", *requirements], stdout=sys.stderr, stderr=sys.stderr)
    if result.returncode:
        raise Problem("setup_failed", "Isolated setup failed. The host should resolve the reported package/network problem; no transcription models were requested.")
    return {"python": str(executable), "next": "Run all helpers with this interpreter. Use an existing supported Node/Deno runtime or let the host set one up locally. doctor reports availability; actual retrieval verifies compatibility."}


def dispatch(args):
    command = args.command
    if command == "doctor":
        return retrieval.doctor()
    if command == "bootstrap":
        return bootstrap(args.env_dir, args.visual)
    if command == "prepare":
        return runs.prepare(args.url, args.work_dir, transcript=args.transcript, metadata=args.metadata, language=args.language, budget=args.unit_tokens, transcription_method=args.transcription_method, consent_run=args.consent_run)
    directory = args.run_dir.resolve()
    if command in {"status", "resume"}:
        return runs.status(directory, details=args.details)
    if command == "read":
        if args.unit:
            return runs.read_unit(directory, args.unit)
        if args.start is not None and args.end is not None:
            return runs.read_range(directory, args.start, args.end)
        raise Problem("invalid_read", "Use --unit or both --start and --end.")
    if command == "record":
        return runs.record(directory, args.file)
    if command == "review":
        return runs.review(directory, args.file)
    if command == "consent":
        return runs.consent(directory, args.choice)
    if command == "frames":
        if not importlib.util.find_spec("PIL"):
            raise Problem("missing_dependency", "Set up Pillow and FFmpeg with bootstrap --visual before frame extraction.")
        from .visuals import frames
        result = frames(directory, media=args.media, overview=args.overview, start=args.start, end=args.end, every=args.every, detail=args.detail, scene_detection=not args.no_scenes)
        result["frame_count"] = len(result.pop("frames"))
        return result
    if command == "audio":
        run = runs.load(directory)
        if run["transcription"]["consent"] != "granted":
            raise Problem("consent_required", "Obtain and record explicit user consent before downloading audio for local transcription.")
        path = retrieval.download_media(run["video_id"], directory / "media", "audio")
        return {"audio": str(path), "next": "Host configures its chosen free local transcriber and imports timed results. No paid endpoint is authorized."}
    if command == "map":
        value = read_json(args.file)
        if not isinstance(value, dict):
            raise Problem("invalid_map", "Output map must be an object keyed by unit IDs.")
        atomic_json(directory / "output-map.json", value)
        run = runs.load(directory)
        run["phase"] = "analyzing"
        atomic_json(directory / "run.json", run)
        return {"output_map": str(directory / "output-map.json")}
    if command == "validate":
        return validation.validate(directory, args.output, accept_findings=args.accept_findings)
    raise Problem("unknown_command", "Unsupported command.")


def main():
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args()
    try:
        result = dispatch(args)
        incomplete = result.get("status") in {"incomplete", "awaiting_source"}
        print(json.dumps({"ok": not incomplete, **result}, ensure_ascii=False, indent=None if args.command == "read" else 2, separators=(",", ":") if args.command == "read" else None, allow_nan=False))
        raise SystemExit(2 if incomplete else 0)
    except Problem as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": str(exc)}}, ensure_ascii=False))
        raise SystemExit(2)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": {"code": "invalid_input_or_io", "message": f"{type(exc).__name__}; verify input files and write permissions."}}))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
