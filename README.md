# tldw

Turn a YouTube tutorial, lecture, or workshop into an Agent Skill that can **apply its teaching**: procedures, decision rules, worked examples, and troubleshooting, backed by timestamps.

Free extraction. No API key. Your existing agent does the synthesis. Built for ten-minute videos and multi-hour recordings through resumable source processing.

## Use it

Install this repository as an Agent Skill using your harness's skill installer, or copy the repository into a discoverable `tldw` skill folder. For hosts supported by the Skills CLI:

```sh
npx skills add https://github.com/jpmachado1189/tldw --skill tldw
```

Then ask your agent:

```text
Use tldw to turn https://www.youtube.com/watch?v=VIDEO_ID
into a skill I can use to apply its teaching. Save it in ./my-new-skill.
```

The agent handles lightweight utility setup when necessary and permitted. You do not need to configure a model account or GPU. The normal path retrieves existing captions and uses your agent's image capabilities to inspect selected frames.

The visual path uses cached preview frames and bounded detail requests. On-screen teaching can be recorded directly against inspected frames without a caption anchor. An explicitly selected visual-only run can process silent demonstrations; it discloses that audio was not verified.

When captions are unavailable and spoken teaching is needed, a timed transcript you provide or optional free local transcription can recover it. **The skill waits for consent before downloading transcription models or processing audio that way.** The normal caption-and-visual path requires no transcription model.

## What happens

1. **Retrieve:** metadata, original-language captions where identifiable, and timestamped source text.
2. **Inspect:** regular/scene/chapter/cue samples across the duration, then closer review of demonstrations, diagrams, slides, and code. Detail downloads request short clips; if the server cannot provide a usable section, one cached full detail file is reused. Returned media is decoded before accepting a detail download.
3. **Extract teaching:** bounded reading units, evidence records, qualifications, examples, and failure modes.
4. **Build:** a compact skill entry point and task-oriented references with source links.
5. **Verify:** segment ownership, processing records, output mapping, timestamps, file links, suspicious instructions, and a host-run application exercise.

Progress is saved by source/configuration identity. A five-hour transcript is read in bounded pieces; the end is not discarded when a context window fills. The generated skill is organized around useful tasks, not forced into the video's chronology.

## Requirements and limits

- A harness with shell execution, network access, and file reading/writing; Python 3.10+ (the host can arrange it). Image inspection enables visual interpretation.
- Free utilities: yt-dlp, a supported Node/Deno runtime for YouTube challenge solving, and the caption fallback package. FFmpeg/Pillow enable frames and contact sheets. [Setup details](references/setup.md).
- No paid extraction API or local transcription model is required on the normal caption path. Downloads use bandwidth/storage, and synthesis uses the host's normal usage allowance.
- YouTube can block automated retrieval. Private, deleted, restricted, unfinished, or otherwise inaccessible videos are not guaranteed. The tool does not automatically export browser credentials.
- Visual coverage is **adaptive sampling**, not every frame. A host without image understanding can produce a transcript-grounded result with an explicit visual limitation.
- Untimed prose and third-party summaries cannot establish full video coverage. Captions may contain transcription errors. Validation is not a semantic-fidelity certificate.
- One completed video per run. No playlist conversion, channel crawling, active livestreams, or automatic publication of generated skills.

See [VALIDATION.md](VALIDATION.md) for actual tested coverage and remaining limitations. Codex is the first behavioral test harness; do not infer that every other harness has been verified.

## Helper CLI

From a checkout, using a suitable interpreter:

```sh
python scripts/tldw.py doctor
python scripts/tldw.py bootstrap --env-dir /path/outside/repo/tools --visual
# Use the interpreter returned by bootstrap for subsequent calls.
python scripts/tldw.py prepare 'YOUTUBE_URL' --work-dir /path/outside/repo/runs
python scripts/tldw.py resume --run-dir RUN_DIRECTORY
python scripts/tldw.py read --run-dir RUN_DIRECTORY --unit u0001
python scripts/tldw.py frames --run-dir RUN_DIRECTORY --overview
python scripts/tldw.py frames --run-dir RUN_DIRECTORY --start 120 --end 140 --every 2 --detail
```

The CLI extracts and tracks evidence. It deliberately does not call a model or generate skill prose automatically. The host follows [SKILL.md](SKILL.md), records its analysis, writes the generated skill, and runs validation. All helper commands return JSON; errors/incomplete work use exit code 2. [Evidence and interfaces](references/evidence.md).

For standalone on-screen evidence outside existing transcript units, use `visual-unit --run-dir RUN_DIRECTORY --start 120 --end 150`. For an explicitly visual-only source, use `prepare URL --work-dir WORK_DIRECTORY --visual-only`. The previous `scripts/youtube_to_skill.py` entry point remains a compatibility wrapper.

## Development

```sh
python -m venv .venv
# Activate this environment using your platform's normal command.
python -m pip install -e '.[extract,visual,test]'
python -m pytest -q
python -m ruff check .
```

Tests use synthetic source text/media and mock network failures. Live tests are separate and do not publish transcripts or downloaded media. Keep working corpora, environments, models, generated user skills, cookies, and raw logs outside this public repository.

## License and acknowledgments

MIT. Inspired by [book-to-skill](https://github.com/virgiliojr94/book-to-skill)'s separation of extraction, agent synthesis, and on-demand references. This repository contains an original implementation focused on timed video evidence and resumable coverage.

Uses separately distributed free/open-source utilities; their licenses apply to those utilities. The converter's license does not grant rights to republish third-party video content. Generated outputs remain local unless their user separately requests publication.
