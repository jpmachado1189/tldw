import subprocess
from pathlib import Path

import pytest

from ytskill import retrieval, runs
from ytskill.common import Problem, atomic_json
from ytskill.visuals import frames, overview_times
from test_workflow import supplied


def test_overview_always_spans_five_hours():
    times, info = overview_times(18000, list(range(18000)), [], [])
    assert len(times) <= 900
    assert times[0] == 0
    assert times[-1] >= 17999
    assert all(any(abs(t - expected) < .1 for t in times) for expected in range(0, 18000, 60))
    assert info["exhaustive"] is False


def test_visual_gap_in_review_is_not_complete(tmp_path):
    directory = supplied(tmp_path)
    review = tmp_path / "visual-review.json"
    atomic_json(review, {"visuals": {"capability": "available", "reviews": [{"start": 0, "end": 20, "level": "sampled", "notes": "Only beginning inspected."}]}})
    runs.review(directory, review)
    from test_workflow import acknowledge, generated
    acknowledge(directory, tmp_path)
    output = generated(tmp_path, directory)
    runs.review(directory, review)
    from ytskill.validation import validate
    report = validate(directory, output)
    assert any("does not span" in e for e in report["errors"])


def test_partial_media_not_accepted(tmp_path, monkeypatch):
    (tmp_path / "preview.webm.part").write_bytes(b"partial")
    calls = []
    def failed(arguments, timeout):
        calls.append(arguments)
        raise Problem("network_error", "Download interrupted")
    monkeypatch.setattr(retrieval, "ytdlp", failed)
    with pytest.raises(Problem):
        retrieval.download_media("AbCdEfGh123", tmp_path)
    assert calls


def test_ffmpeg_extracts_synthetic_visual_only_instruction(tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("imageio_ffmpeg")
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (640, 360), "white")
    ImageDraw.Draw(image).text((40, 100), "VISUAL ONLY: TURN THE BLUE SWITCH OFF", fill="black", font_size=22)
    image.save(tmp_path / "slide.png")
    video = tmp_path / "demo.mp4"
    result = subprocess.run([retrieval.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(tmp_path / "slide.png"), "-t", "4", "-pix_fmt", "yuv420p", str(video)], capture_output=True)
    assert result.returncode == 0
    directory = supplied(tmp_path, [{"start": 0, "end": 4, "text": "Use the setting shown on screen."}], duration=4)
    result = frames(directory, media=video, start=0, end=4, every=2)
    assert len(result["frames"]) == 2
    assert all(x["width"] == 640 and x["height"] == 360 for x in result["frames"])
    assert result["contact_sheets"]
    assert result["status"] == "extracted_not_reviewed"
    assert runs.load(directory)["visuals"]["capability"] == "unknown"
    for relative in result["contact_sheets"]:
        assert (Path(directory) / relative).is_file()
