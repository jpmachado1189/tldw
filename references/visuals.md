# Adaptive visual review

The host's image understanding supplies interpretation; no additional vision model or OCR service is required. Ask the helper to extract an overview:

```text
PYTHON SKILL_ROOT/scripts/tldw.py frames --run-dir RUN_DIRECTORY --overview
```

The helper downloads a preview (up to 480p when available), scans scene changes at 1 fps, combines those with regular samples, chapter starts, and common English screen-reference cues, and creates timestamped contact sheets. Scene detection is checkpointed in 20-minute intervals. Regular samples ensure non-English material and missed cue phrases still receive an overview across the duration. For recordings up to five hours, regular samples are one minute apart; the overview budget is 900 frames. The sampling manifest records the policy and selected frames. Fast or subtle actions can still be missed.

Inspect every returned sheet in small batches; contact sheets show where to look, not necessarily readable code. Note which intervals appear to contain slides, screens, diagrams, or physical demonstrations. Expand those intervals around the steps actually being taught:

```text
PYTHON SKILL_ROOT/scripts/tldw.py frames --run-dir RUN_DIRECTORY --start 120 --end 150 --every 2 --detail
```

Detail mode requests the selected interval at up to 1080p when available, using yt-dlp/FFmpeg section downloading and preferring direct HTTP video formats. Each requested detail interval is capped at five minutes and each frame request at 120 images; split larger requests. Clips are decoded at the requested beginning and end before being accepted. The clip is cached with a completion marker, and its local timestamps are translated back to absolute video time in every frame and evidence manifest. A section attempt is bounded to two minutes. When a format cannot deliver a usable section, the helper downloads one full detail file, verifies the requested frames, and reuses that file on subsequent requests instead of repeating failed seeks. This fallback and its reason are recorded in the download sidecars; it uses more bandwidth. A timeout stops the utility's child processes as well.

With `--media`, the input is treated as the full original timeline and uses that file's actual resolution: a preview cannot become high resolution by requesting detail. Do not pass an offset clip as if it were a full video. The manifest records actual width/height separately from requested maximum width; do not infer resolution from the filename suffix. Request smaller intervals when actions are rapid. Inspect full-size images for exact code, equations, settings, or table entries. Pair before/after frames when meaning depends on a change. OCR is optional assistance; no paid vision endpoint or local vision model is required.

For a user-supplied accessible video file:

```text
PYTHON SKILL_ROOT/scripts/tldw.py frames --run-dir RUN_DIRECTORY --media LOCAL_VIDEO --overview
```

Verify that the local file is the requested source before using its visuals. `--no-scenes` permits regular/chapter/cue sampling when a scene pass is too expensive or fails; record that reduction. Download or decode failures are retained as failures, not silently counted as inspected content. Media downloads use completion markers so partial files are never accepted as finished.

Record visual findings with `source_frames` alongside transcript-supported claims. Where speech says only "do this," describe the observed action and cite its registered frame and timestamp. A visual claim does not require a caption anchor. Add a bounded `visual-unit` for on-screen teaching outside existing units. For a source without usable captions, explicit `--visual-only` preparation creates a tracked visual timeline; its result covers inspected on-screen teaching and must disclose that audio was not verified. In a caption-based run, a gap remains unresolved until its actual missing material is assessed.

Submit the review ledger after inspection. Include every interval as sampled, close-reviewed, or unresolved. State adaptive-sampling limits in the generated source reference and final response. Do not mark an entire five-hour video closely reviewed because a handful of frames were opened.
