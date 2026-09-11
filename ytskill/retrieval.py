from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import re
from pathlib import Path

from .common import Problem, canonical_url, execute, finite, read_json


def yt_command() -> list[str]:
    override = os.environ.get("YTS_YTDLP")
    if override:
        return [override]
    if importlib.util.find_spec("yt_dlp"):
        return [sys.executable, "-m", "yt_dlp"]
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    raise Problem("missing_dependency", 'Set up yt-dlp in an isolated environment, e.g. pip install "yt-dlp[default]".')


def yt_flags() -> list[str]:
    flags = ["--ignore-config", "--no-plugin-dirs", "--no-playlist", "--no-progress", "--no-warnings", "--socket-timeout", "20", "--retries", "2", "--extractor-retries", "2"]
    runtime = os.environ.get("YTS_JS_RUNTIME")
    if runtime:
        flags += ["--js-runtimes", runtime]
    elif shutil.which("node"):
        flags += ["--js-runtimes", "node"]
    return flags


def classify(message: str) -> str:
    lower = message.lower()
    if any(x in lower for x in ["429", "too many requests", "ipblocked", "requestblocked", "not a bot", "po token", "po_token"]):
        return "access_blocked"
    if any(x in lower for x in ["private video", "age-restricted", "age restricted", "members-only", "not available in your country", "sign in", "video unavailable", "copyright", "videounavailable"]):
        return "restricted_video"
    if any(x in lower for x in ["transcriptsdisabled", "notranscriptfound", "no subtitles", "no captions"]):
        return "no_captions"
    if any(x in lower for x in ["timed out", "timeout", "connection", "network", "unable to download", "resolve", "403", "ssl"]):
        return "network_error"
    return "extraction_error"


def failure_text(code: str) -> str:
    return {
        "access_blocked": "YouTube blocked automated retrieval. Retry later or supply a transcript/media file; do not assume captions are absent.",
        "restricted_video": "The video is unavailable or restricted. Supply material you can access; automatic authentication is not attempted.",
        "no_captions": "No usable captions were available. Offer free local transcription; obtain consent before downloading models or transcribing.",
        "network_error": "Retrieval failed because of a network or HTTP error. Saved work is retained.",
    }.get(code, "The extraction utility failed. Check its installed version and the source's availability.")


def ytdlp(arguments: list[str], timeout=180):
    result = execute(yt_command() + yt_flags() + arguments, timeout=timeout)
    if result.returncode:
        code = classify(result.stderr)
        # Do not echo raw stderr: it can contain signed media URLs and private paths.
        raise Problem(code, failure_text(code))
    return result


def inspect(identity: str) -> dict:
    result = ytdlp(["--skip-download", "--dump-single-json", "--", canonical_url(identity)])
    try:
        info = json.loads(result.stdout)
    except ValueError as exc:
        raise Problem("invalid_metadata", "yt-dlp returned invalid metadata JSON.") from exc
    if info.get("id") != identity:
        raise Problem("source_mismatch", "Returned video ID does not match the requested source.")
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming", "post_live"}:
        raise Problem("incomplete_video", "Only completed, processed video recordings are supported.")
    return info


def public_metadata(info: dict) -> dict:
    duration = finite(info.get("duration"), "video duration")
    return {
        "id": info["id"], "url": canonical_url(info["id"]),
        "title": info.get("title") or info["id"], "channel": info.get("channel") or info.get("uploader") or "unknown",
        "duration": duration, "description": info.get("description") or "", "language": info.get("language"),
        "chapters": [{k: c.get(k) for k in ["start_time", "end_time", "title"]} for c in info.get("chapters") or []],
        "available_tracks": [{"language": language, "generated": kind == "automatic_captions"} for kind in ["subtitles", "automatic_captions"] for language in (info.get(kind) or {}) if language != "live_chat"],
    }


def select_track(info: dict, requested: str | None = None, *, generated_only=False):
    tracks = []
    for kind in ["subtitles", "automatic_captions"]:
        for language, formats in (info.get(kind) or {}).items():
            if language != "live_chat" and formats:
                tracks.append({"language": language, "generated": kind == "automatic_captions", "formats": formats})
    if not tracks:
        raise Problem("no_captions", failure_text("no_captions"))
    original = info.get("language")
    original_marked = [x["language"] for x in tracks if x["language"].endswith("-orig")]
    if not original and original_marked:
        original = original_marked[0].removesuffix("-orig")
    desired = requested or original
    if not desired:
        base_languages = {x["language"].removesuffix("-orig") for x in tracks}
        if len(base_languages) == 1:
            desired = next(iter(base_languages))
        else:
            raise Problem("language_ambiguous", "Original language is unknown and multiple tracks exist. The host should identify it and retry with --language.")
    def matches(code):
        code = code.removesuffix("-orig")
        return code == desired or code.split("-")[0] == desired.split("-")[0]
    matching = [x for x in tracks if matches(x["language"])]
    if generated_only:
        matching = [x for x in matching if x["generated"]]
    if not matching:
        raise Problem("no_captions", "No captions in the selected source language. Choose an available track explicitly or offer local transcription.")
    chosen = min(matching, key=lambda x: (x["generated"], not x["language"].endswith("-orig"), x["language"] != desired))
    return {
        "language": chosen["language"], "generated": chosen["generated"], "original_language": original,
        "translation": "unknown" if not original else (chosen["language"].removesuffix("-orig").split("-")[0] != original.split("-")[0]),
        "method": "yt-dlp",
    }


def fetch_track(identity: str, selection: dict, directory: Path) -> tuple[str, str]:
    before = set(directory.iterdir())
    ytdlp([
        "--skip-download", "--write-auto-subs" if selection["generated"] else "--write-subs",
        "--sub-langs", "^" + selection["language"] + "$", "--sub-format", "json3/vtt/srt",
        "-o", str(directory / "captions.%(ext)s"), "--", canonical_url(identity),
    ])
    files = [p for p in directory.iterdir() if p not in before and p.suffix in {".json3", ".vtt", ".srt"}]
    if not files:
        raise Problem("no_captions", failure_text("no_captions"))
    chosen = sorted(files)[0]
    return chosen.read_text(encoding="utf-8-sig"), chosen.suffix.lstrip(".")


def alternative(identity: str, language: str | None = None) -> tuple[str, str, dict]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from requests import Session
    except ImportError as exc:
        raise Problem("missing_dependency", "Set up youtube-transcript-api to try alternative free caption retrieval.") from exc
    class TimedSession(Session):
        def request(self, *args, **kwargs):
            kwargs.setdefault("timeout", 25)
            return super().request(*args, **kwargs)
    try:
        tracks = list(YouTubeTranscriptApi(http_client=TimedSession()).list(identity))
        candidates = [t for t in tracks if language and t.language_code.split("-")[0] == language.removesuffix("-orig").split("-")[0]]
        if not language and len({t.language_code for t in tracks}) == 1:
            candidates = tracks
        if not candidates:
            raise Problem("language_ambiguous" if tracks and not language else "no_captions", "Alternative retrieval has no unambiguous original-language track. Select --language or offer transcription.")
        track = min(candidates, key=lambda t: t.is_generated)
        fetched = track.fetch()
        return json.dumps(fetched.to_raw_data(), ensure_ascii=False), "json", {"language": track.language_code, "generated": track.is_generated, "translation": False, "method": "youtube-transcript-api"}
    except Problem:
        raise
    except Exception as exc:
        code = classify(type(exc).__name__ + " " + str(exc))
        raise Problem(code, failure_text(code)) from exc


def ffmpeg() -> str:
    if os.environ.get("YTS_FFMPEG"):
        return os.environ["YTS_FFMPEG"]
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise Problem("missing_dependency", "Set up FFmpeg or imageio-ffmpeg for portable frame extraction.") from exc


def doctor() -> dict:
    try:
        yt = execute(yt_command() + ["--version"], timeout=15).stdout.strip()
    except Problem:
        yt = None
    try:
        media = execute([ffmpeg(), "-version"], timeout=15).returncode == 0
    except Problem:
        media = False
    runtime = os.environ.get("YTS_JS_RUNTIME") or shutil.which("deno") or shutil.which("node")
    return {"python": sys.version.split()[0], "yt_dlp": yt, "javascript_runtime": runtime, "ffmpeg": media,
            "caption_fallback": bool(importlib.util.find_spec("youtube_transcript_api")), "contact_sheets": bool(importlib.util.find_spec("PIL")),
            "local_transcription": "optional; explicit consent required; no model installed by this tool"}


def download_media(identity: str, directory: Path, kind="preview") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    # The sidecar binds completed bytes to the requested video and mode. A .part
    # file is never accepted as complete, even when a download was interrupted.
    marker = directory / f"{kind}.download.json"
    if marker.exists():
        saved = read_json(marker)
        candidate = directory / saved.get("filename", "")
        if saved.get("video_id") == identity and candidate.is_file() and candidate.resolve().parent == directory.resolve() and candidate.stat().st_size == saved.get("bytes"):
            return candidate
    selector = "bestaudio/best" if kind == "audio" else "bestvideo[height<=480][protocol=https]/bestvideo[height<=480]/best[height<=480]/worst" if kind == "preview" else "bestvideo[height<=1080][protocol=https]/bestvideo[height<=1080]/best[height<=1080]/best"
    result = ytdlp(["--no-simulate", "--abort-on-unavailable-fragments", "--fragment-retries", "1", "-f", selector, "-o", str(directory / f"{kind}.%(ext)s"), "--print", "after_move:filepath", "--", canonical_url(identity)], timeout=7200)
    paths = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    if not paths or not paths[-1].is_file() or paths[-1].suffix == ".part" or paths[-1].resolve().parent != directory.resolve():
        raise Problem("incomplete_download", "Media download did not produce a verified completed file.")
    from .common import atomic_json
    path = paths[-1]
    atomic_json(marker, {"video_id": identity, "kind": kind, "filename": path.name, "bytes": path.stat().st_size})
    return path


def video_has_frame(path: Path, time=0) -> bool:
    """An empty MP4 can be reported as a successful download; actually decode it."""
    try:
        result = execute([ffmpeg(), "-hide_banner", "-nostdin", "-ss", str(time), "-i", str(path), "-map", "0:v:0", "-vf", "showinfo", "-frames:v", "1", "-f", "null", "-"], timeout=30)
        return result.returncode == 0 and bool(re.search(r"\bn:\s*0\b", result.stderr))
    except Problem:
        return False


def download_detail_clip(identity: str, directory: Path, start, end) -> tuple[Path, float]:
    """Request only a bounded high-resolution interval; keep absolute offset outside the clip."""
    from .common import atomic_json, digest
    start, end = finite(start), finite(end)
    if end <= start or end - start > 300:
        raise Problem("invalid_range", "Request a high-resolution interval of at most five minutes.")
    directory.mkdir(parents=True, exist_ok=True)
    key = digest({"video_id": identity, "start": start, "end": end, "height": 1080, "cuts": "direct-reencode-v2"})[:16]
    marker = directory / f"detail-{key}.download.json"
    failed_cached_clip = False
    if marker.exists():
        saved = read_json(marker)
        candidate = directory / saved.get("filename", "")
        if saved.get("video_id") == identity and saved.get("start") == start and saved.get("end") == end and candidate.is_file() and candidate.resolve().parent == directory.resolve() and candidate.stat().st_size == saved.get("bytes"):
            offset = saved.get("timeline_offset", start)
            if video_has_frame(candidate, max(0, start - offset)) and video_has_frame(candidate, max(0, end - offset - .2)):
                return candidate, offset
            failed_cached_clip = True
    fallback_marker = directory / "detail-section-fallback.json"
    fallback = read_json(fallback_marker) if fallback_marker.exists() else {}
    fallback_reason = "Previously unusable section download." if failed_cached_clip else "Server/format section download failed."
    if not failed_cached_clip and fallback.get("video_id") != identity:
        try:
            result = ytdlp(["--no-simulate", "--ffmpeg-location", ffmpeg(), "--download-sections", f"*{start}-{end}", "--force-keyframes-at-cuts", "-f", "bestvideo[height<=1080][protocol=https][vcodec^=avc]/bestvideo[height<=1080][protocol=https]/bestvideo[height<=1080]/best", "-o", str(directory / f"detail-{key}.%(ext)s"), "--print", "after_move:filepath", "--", canonical_url(identity)], timeout=120)
            paths = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
            if paths and paths[-1].is_file() and paths[-1].suffix != ".part" and paths[-1].resolve().parent == directory.resolve():
                path = paths[-1]
                if video_has_frame(path) and video_has_frame(path, max(0, end - start - .2)):
                    atomic_json(marker, {"video_id": identity, "start": start, "end": end, "timeline_offset": start, "mode": "section", "filename": path.name, "bytes": path.stat().st_size})
                    return path, start
        except Problem as exc:
            if exc.code in {"restricted_video", "access_blocked", "missing_dependency"}:
                raise
            fallback_reason = f"Section retrieval failed: {exc.code}."
    # Some YouTube formats return an empty section with exit code zero. Fall
    # back once to a reusable full detail file instead of repeating bad seeks.
    path = download_media(identity, directory, "detail")
    if not video_has_frame(path, start) or not video_has_frame(path, max(start, end - .2)):
        raise Problem("incomplete_download", "Neither the section nor cached full detail media contains decodable frames at the requested times.")
    atomic_json(fallback_marker, {"video_id": identity, "reason": fallback_reason, "mode": "cached_full_video"})
    atomic_json(marker, {"video_id": identity, "start": start, "end": end, "timeline_offset": 0, "mode": "cached_full_video", "reason": fallback_reason, "filename": path.name, "bytes": path.stat().st_size})
    return path, 0.0
