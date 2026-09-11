# Adaptive visual review

The host's image understanding supplies interpretation; no additional vision model or OCR service is required. Ask the helper to extract an overview:

```text
PYTHON SKILL_ROOT/scripts/youtube_to_skill.py frames --run-dir RUN_DIRECTORY --overview
```

The helper downloads a preview (up to 480p when available), scans scene changes at 1 fps, combines those with regular samples, chapter starts, and common English screen-reference cues, and creates timestamped contact sheets. Scene detection is checkpointed in 20-minute intervals. Regular samples ensure non-English material and missed cue phrases still receive an overview across the duration. For recordings up to five hours, regular samples are one minute apart; the overview budget is 900 frames. The sampling manifest records the policy and selected frames. Fast or subtle actions can still be missed.

Inspect every returned sheet in small batches; contact sheets show where to look, not necessarily readable code. Note which intervals appear to contain slides, screens, diagrams, or physical demonstrations. Expand those intervals around the steps actually being taught:

```text
PYTHON SKILL_ROOT/scripts/youtube_to_skill.py frames --run-dir RUN_DIRECTORY --start 120 --end 150 --every 2 --detail
```

Detail mode downloads up to 1080p when available. Request smaller time intervals when actions are rapid. Each request is capped at 120 frames. Inspect full-size individual images for exact code, equations, settings, or table entries. Pair before/after frames when the meaning depends on a change. OCR can be arranged locally by the host if useful, but is never required and its output must be checked against images.

For a user-supplied accessible video file:

```text
PYTHON SKILL_ROOT/scripts/youtube_to_skill.py frames --run-dir RUN_DIRECTORY --media LOCAL_VIDEO --overview
```

Verify that the local file is the requested source before using its visuals. `--no-scenes` permits regular/chapter/cue sampling when a scene pass is too expensive or fails; record that reduction. Download or decode failures are retained as failures, not silently counted as inspected content. Media downloads use completion markers so partial files are never accepted as finished.

Record visual findings in the source unit's evidence alongside transcript-supported claims. Where speech says only "do this," describe the action from the image and name the frame and timestamp. An image-only teaching point should be attached to its time interval's unit, clearly marked as visual evidence; a caption gap containing instruction must be recovered before completion. The record validator still requires a source-segment anchor for the unit; it does not pretend that adjacent speech proves a visual claim.

Submit the review ledger after inspection. Include every interval as sampled, close-reviewed, or unresolved. State adaptive-sampling limits in the generated source reference and final response. Do not mark an entire five-hour video closely reviewed because a handful of frames were opened.
