from __future__ import annotations

import math
import re
from pathlib import Path

from .common import Problem, atomic_json, clock, digest, execute, finite, read_json
from .retrieval import download_media, ffmpeg
from .runs import load


CUES = re.compile(r"\b(look (?:here|at|on)|on (?:the |my )?screen|as you can see|this (?:slide|diagram|chart|button)|click|select|change this|type this|watch (?:this|how))\b", re.I)


def scene_times(media: Path, directory: Path, duration: float) -> list[float]:
    """Checkpoint scene passes in 20-minute intervals; sample differences at 1 fps."""
    times = []
    for index, start in enumerate(range(0, math.ceil(duration), 1200)):
        marker = directory / f"scenes-{index:04d}.json"
        if marker.exists():
            times.extend(read_json(marker))
            continue
        result = execute([
            ffmpeg(), "-hide_banner", "-nostdin", "-ss", str(start), "-i", str(media),
            "-t", str(min(1200, duration - start)), "-an", "-vf",
            "fps=1,scale=320:-2,select='gt(scene,0.15)',showinfo", "-f", "null", "-",
        ], timeout=1800)
        if result.returncode:
            raise Problem("visual_decode", "Scene detection failed; try a local media file or retain a visual limitation.")
        found = [round(start + float(x), 3) for x in re.findall(r"pts_time:([\d.]+)", result.stderr)]
        atomic_json(marker, found)
        times.extend(found)
    return times


def overview_times(duration: float, scenes: list[float], chapters: list[dict], segments: list[dict], maximum=900) -> tuple[list[float], dict]:
    # Always span the whole duration. For very long inputs increase the regular
    # interval rather than sampling the beginning and silently dropping the end.
    interval = max(60, math.ceil(duration / (maximum // 2)))
    regular = [float(t) for t in range(0, math.ceil(duration), interval)] + [max(0, duration - .1)]
    cue_times = [x["start"] for x in segments if CUES.search(x["text"])]
    chapter_times = [finite(c["start_time"]) for c in chapters]
    candidates = sorted(set(round(t, 1) for t in scenes + cue_times + chapter_times if 0 <= t < duration))
    chosen = set(regular)
    candidates = [t for t in candidates if all(abs(t - x) >= 2 for x in chosen)]
    allowance = max(0, maximum - len(chosen))
    if len(candidates) > allowance and allowance:
        candidates = [candidates[min(len(candidates) - 1, int(i * len(candidates) / allowance))] for i in range(allowance)]
    elif not allowance:
        candidates = []
    chosen.update(candidates)
    return sorted(chosen), {"regular_interval_seconds": interval, "scene_candidates": len(scenes), "cue_candidates": len(cue_times), "selected_frames": len(chosen), "exhaustive": False}


def frames(directory: Path, *, media: Path | None = None, overview=False, start=0.0, end=None, every=5.0, detail=False, scene_detection=True) -> dict:
    run = load(directory)
    if not run.get("metadata"):
        raise Problem("missing_metadata", "A verified duration is needed before visual sampling.")
    duration = finite(run["metadata"]["duration"])
    if duration <= 0:
        raise Problem("invalid_duration", "Video duration must be positive.")
    if media:
        media = media.resolve(strict=True)
        if not media.is_file():
            raise Problem("missing_media", "Supply a readable media file.")
    else:
        media = download_media(run["video_id"], directory / "media", "detail" if detail else "preview")
    identity = digest({"path": str(media), "size": media.stat().st_size, "mtime": media.stat().st_mtime_ns})[:12]
    scene_dir = directory / "visuals" / identity
    scene_dir.mkdir(parents=True, exist_ok=True)
    if overview:
        scenes = scene_times(media, scene_dir, duration) if scene_detection else []
        transcript = read_json(directory / "transcript.json") if (directory / "transcript.json").exists() else []
        times, sampling = overview_times(duration, scenes, run["metadata"].get("chapters") or [], transcript)
    else:
        start, end, every = finite(start), finite(end if end is not None else min(start + 60, duration)), finite(every)
        if end <= start or end > duration + .1 or every <= 0 or (end - start) / every > 120:
            raise Problem("invalid_range", "Frame range must fit the video, use a positive interval, and request at most 120 frames. Split larger requests.")
        times = [min(duration - .01, start + index * every) for index in range(math.ceil((end - start) / every))]
        sampling = {"interval_seconds": every, "exhaustive": False}
    from PIL import Image, ImageDraw, ImageFont
    width = 1920 if detail else 960
    images, failures = [], []
    for time in times:
        destination = scene_dir / f"frame-{round(time * 1000):010d}-{width}.jpg"
        valid = False
        if destination.exists():
            try:
                with Image.open(destination) as im:
                    im.verify()
                valid = True
            except (OSError, ValueError):
                pass
        if not valid:
            temporary = destination.with_suffix(".pending.jpg")
            result = execute([ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-ss", str(time), "-i", str(media), "-frames:v", "1", "-vf", f"scale='min({width},iw)':-2", "-q:v", "2", str(temporary)], timeout=120)
            if result.returncode or not temporary.exists():
                failures.append(time)
                continue
            try:
                with Image.open(temporary) as im:
                    im.verify()
            except (OSError, ValueError):
                failures.append(time)
                continue
            temporary.replace(destination)
        with Image.open(destination) as im:
            actual_width, actual_height = im.size
        images.append({"time": time, "file": destination.relative_to(directory).as_posix(), "width": actual_width, "height": actual_height, "requested_max_width": width})
    sheets = []
    font = ImageFont.load_default(size=17)
    request_key = digest({"times": times, "width": width})[:10]
    for offset in range(0, len(images), 12):
        batch = images[offset:offset + 12]
        sheet = Image.new("RGB", (1280, math.ceil(len(batch) / 4) * 210), "#151515")
        draw = ImageDraw.Draw(sheet)
        for index, entry in enumerate(batch):
            x, y = (index % 4) * 320, (index // 4) * 210
            with Image.open(directory / entry["file"]) as im:
                im.thumbnail((318, 180))
                sheet.paste(im, (x, y))
            draw.text((x + 5, y + 185), clock(entry["time"]), fill="white", font=font)
        path = scene_dir / f"sheet-{request_key}-{offset // 12 + 1:03d}.jpg"
        sheet.save(path, quality=90)
        sheets.append(path.relative_to(directory).as_posix())
    manifest = {"schema_version": 1, "video_id": run["video_id"], "sampling": sampling, "frames": images, "contact_sheets": sheets, "failed_timestamps": failures,
                "status": "extracted_not_reviewed", "next": "The host must inspect these images, expand teaching-heavy intervals, and record reviews. Extraction does not count as visual understanding."}
    manifest_path = scene_dir / f"manifest-{request_key}.json"
    atomic_json(manifest_path, manifest)
    return {"run_dir": str(directory.resolve()), "manifest": manifest_path.relative_to(directory).as_posix(), **manifest}
