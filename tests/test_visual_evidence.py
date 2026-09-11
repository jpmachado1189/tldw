import subprocess
from pathlib import Path

import pytest

from ytskill import retrieval, runs, validation, visuals
from ytskill.common import Problem, atomic_json
from test_workflow import VIDEO, supplied


def silent_media(tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("imageio_ffmpeg")
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (640, 360), "white")
    ImageDraw.Draw(image).text((20, 80), "Turn the blue switch OFF before export.", fill="black", font_size=22)
    image.save(tmp_path / "instruction.png")
    media = tmp_path / "silent.mp4"
    result = subprocess.run([retrieval.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(tmp_path / "instruction.png"), "-t", "4", "-an", "-pix_fmt", "yuv420p", str(media)], capture_output=True)
    assert result.returncode == 0
    return media


def test_silent_video_produces_frame_grounded_evidence_without_fake_captions(tmp_path, monkeypatch):
    meta = tmp_path / "metadata.json"
    atomic_json(meta, {"id": VIDEO, "duration": 4, "title": "Silent instruction"})
    monkeypatch.setattr(retrieval, "fetch_track", lambda *a: pytest.fail("Visual-only preparation must not request captions."))
    directory = Path(runs.prepare(VIDEO, tmp_path / "runs", metadata=meta, visual_only=True)["run_dir"])
    run, transcript = runs.source(directory)
    assert transcript == [] and not runs.integrity(run, transcript)
    assert len(run["units"]) == 1
    assert runs.prepare(VIDEO, tmp_path / "runs", metadata=meta, visual_only=True)["run_dir"] == str(directory)
    extracted = visuals.frames(directory, media=silent_media(tmp_path), start=0, end=4, every=2)
    frame = extracted["frames"][0]
    unit = run["units"][0]
    record = {"unit_id": unit["id"], "disposition": "incorporated", "reason": "The setting instruction is on screen.", "segment_ids": [], "evidence": [{"claim": "Turn the blue switch off before export.", "start": 0, "end": 2, "source_frames": [{"file": frame["file"], "time": frame["time"], "observation": "The slide states the switch must be off before export."}]}], "unresolved": []}
    atomic_json(tmp_path / "record.json", record)
    runs.record(directory, tmp_path / "record.json")
    output = tmp_path / "generated"
    output.mkdir()
    (output / "SKILL.md").write_text(f'---\nname: switch-export\ndescription: "Prepare the switch before export."\n---\nTurn the blue switch off before export.\n[Evidence](https://www.youtube.com/watch?v={VIDEO}&t=0)\n', encoding="utf-8")
    atomic_json(directory / "output-map.json", {unit["id"]: {"disposition": "incorporated", "files": ["SKILL.md"]}})
    incomplete = validation.validate(directory, output)
    assert any("inspected-frame ledger" in e for e in incomplete["errors"])
    atomic_json(tmp_path / "review.json", {"visuals": {"capability": "available", "reviews": [{"start": 0, "end": 4, "level": "sampled", "notes": "Synthetic fixed slide fixture.", "frame_files": [f["file"] for f in extracted["frames"]]}]}})
    runs.review(directory, tmp_path / "review.json")
    completed = validation.validate(directory, output)
    assert completed["status"] == "verified_with_limits"
    assert any("audio" in s for s in completed["limitations"])
    # Neither arbitrary files nor valid frames relabeled to a different time work.
    record["evidence"][0]["source_frames"][0]["time"] = 1
    assert runs.validate_record(run, transcript, record, frames=runs.frame_catalog(directory, run))
    record["evidence"][0]["source_frames"][0].update(time=0, file="unregistered.jpg")
    assert runs.validate_record(run, transcript, record, frames=runs.frame_catalog(directory, run))


def test_silent_timeline_cannot_lose_middle_or_end(tmp_path):
    metadata = tmp_path / "meta.json"
    atomic_json(metadata, {"id": VIDEO, "duration": 18000})
    directory = Path(runs.prepare(VIDEO, tmp_path / "runs", metadata=metadata, visual_only=True)["run_dir"])
    run, transcript = runs.source(directory)
    assert len(run["units"]) == 60 and not runs.integrity(run, transcript)
    run["units"].pop(30)
    assert any("interval" in e for e in runs.integrity(run, transcript))
    run["units"].pop()
    assert any("full video" in e for e in runs.integrity(run, transcript))


def test_supplemental_visual_unit_is_bounded_and_idempotent(tmp_path):
    directory = supplied(tmp_path)
    original = len(runs.load(directory)["units"])
    unit = runs.add_visual_unit(directory, 50, 90)["unit"]
    assert unit["segment_ids"] == []
    assert runs.add_visual_unit(directory, 50, 90)["unit"] == unit
    assert len(runs.load(directory)["units"]) == original + 1
    assert not runs.integrity(*runs.source(directory))
    with pytest.raises(Problem):
        runs.add_visual_unit(directory, 10, 400)


def test_detail_clip_reads_relative_time_and_reports_absolute_time(tmp_path, monkeypatch):
    media = silent_media(tmp_path)
    directory = supplied(tmp_path)
    calls = []
    def download(identity, destination, start, end):
        calls.append((start, end))
        return media, start
    monkeypatch.setattr(visuals, "download_detail_clip", download)
    result = visuals.frames(directory, start=60, end=64, every=2, detail=True)
    assert calls == [(60, 64)]
    assert result["timeline_offset"] == 60
    assert [f["time"] for f in result["frames"]] == [60, 62]
    assert not result["failed_timestamps"]


def test_detail_download_is_bounded_cached_and_uses_section_cut(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(retrieval, "ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(retrieval, "video_has_frame", lambda *a: True)
    def download(args, timeout):
        calls.append(args)
        output = Path(args[args.index("-o") + 1].replace("%(ext)s", "mp4"))
        output.write_bytes(b"finished fixture")
        return subprocess.CompletedProcess(args, 0, stdout=str(output), stderr="")
    monkeypatch.setattr(retrieval, "ytdlp", download)
    first = retrieval.download_detail_clip(VIDEO, tmp_path, 300, 310)
    assert retrieval.download_detail_clip(VIDEO, tmp_path, 300, 310) == first
    assert len(calls) == 1 and "*300.0-310.0" in calls[0]
    assert "--force-keyframes-at-cuts" in calls[0]
    with pytest.raises(Problem):
        retrieval.download_detail_clip(VIDEO, tmp_path, 0, 18000)


def test_empty_section_falls_back_once_without_accepting_invalid_video(tmp_path, monkeypatch):
    calls = []
    full = tmp_path / "detail.mp4"
    full.write_bytes(b"valid fixture")
    monkeypatch.setattr(retrieval, "ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(retrieval, "video_has_frame", lambda p, *a: p == full)
    monkeypatch.setattr(retrieval, "download_media", lambda *a: full)
    def empty(args, timeout):
        calls.append(args)
        output = Path(args[args.index("-o") + 1].replace("%(ext)s", "mp4"))
        output.write_bytes(b"empty header")
        return subprocess.CompletedProcess(args, 0, stdout=str(output), stderr="")
    monkeypatch.setattr(retrieval, "ytdlp", empty)
    assert retrieval.download_detail_clip(VIDEO, tmp_path, 300, 310) == (full, 0)
    assert retrieval.download_detail_clip(VIDEO, tmp_path, 600, 610) == (full, 0)
    assert len(calls) == 1
