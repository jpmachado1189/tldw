# Validation record

Date: 2026-09-11. Version: 0.1.1. The converter is portable by design; the complete interactive workflow was verified first in Codex on Windows. Other harnesses require their own behavioral verification.

## Automated checks

The offline pytest suite covers:

- Single-video URL normalization and rejection of playlist/channel/non-YouTube targets.
- Manual, JSON3, automatic rolling, Unicode, and malformed captions; preservation of literal code comparisons.
- Five-hour synthetic transcripts with a critical final exception, exact segment ownership, bounded units, and oversized non-whitespace cues.
- Caption-track language selection and recovery from a truncated manual track using an automatic track.
- Missing captions, declined consent, consented local-transcript import, and source identity checks.
- Checkpoint resume, configuration changes, tamper detection, and interrupted media downloads.
- Real FFmpeg extraction/contact-sheet creation from a synthetic visual-only instruction.
- Missing/unresolved evidence, caption gaps, incomplete visual ledgers, malformed metadata, broken file/heading links, invalid timestamps, and nested suspicious instructions.

Local result: **55 tests passed**, Ruff passed, and the Codex skill-creator validator passed. An editable package install and the helper's own `bootstrap --visual` operation into a fresh isolated environment also succeeded. No ASR model was installed.

Run `python -m pytest -q` and `python -m ruff check .` from the checkout. CI runs the offline suite on Windows, Ubuntu, and macOS with Python 3.10 and 3.12. CI status is separate from behavioral harness support.

## Live extraction checks

Raw test material remains local, outside this repository.

| Source | Observed result |
|---|---|
| [Corey Schafer: Windows venv tutorial](https://www.youtube.com/watch?v=APOPm01BVrk) | Retrieved a 17:09 tutorial's captions, extracted 35 timestamped preview frames and three contact sheets, with no failed frame requests in the overview. |
| [Programming with Mosh: Python course](https://www.youtube.com/watch?v=_uQrJ0TkZlc) | Verified duration 6:14:07. The selected manual captions left a 4,143-second tail gap. Comparing the automatic original-English track recovered coverage through the end, with no remaining detected gaps over 30 seconds. Normalized 9,993 caption segments; ownership check passed. |
| [Nick Saraev: Cold Email Copywriting & Outreach](https://www.youtube.com/watch?v=uSTGNHGFOAo) | Verified duration 3:59:11. Retrieved original-English automatic captions: 8,029 segments, 51,987 words, 84 bounded reading units, all 29 chapters represented, no detected gaps over 30 seconds, and no missing or multiply owned segments. Largest serialized source-read estimate: 3,035 tokens. Extracted 597 adaptive overview frames on 50 contact sheets without failed requests, through the final second. |

The long-course test verifies retrieval, gap handling, and bounded source preparation. It is **not** a claim that the entire six-hour course was synthesized and behaviorally evaluated. Gap detection is heuristic; zero detected gaps does not establish word-perfect transcription.

The Nick Saraev exploration read five complete units distributed across the recording, plus a short boundary passage. It inspected five of the 50 overview sheets, a coarse eight-frame contact sheet, and five closer samples of a late follow-up diagram. The incomplete-output gate correctly rejected the remaining 79 units and two unresolved example/procedure boundaries. This is a retrieval, visual-access, evidence, and resume check, not full four-hour synthesis or a completed generated skill.

The live repeat-run test exposed a resume defect: YouTube alternated `en-US` and `en` in original-language metadata despite returning identical captions. Version 0.1.1 normalizes these descriptive labels for identity comparison and recognizes older equivalent checkpoints. The live retest preserved all five evidence records byte-for-byte and resumed at the first pending unit. Three additional regression tests cover legacy-checkpoint reuse, conflicting progress, and preservation of distinct selected caption tracks/requested languages; changed source text still produces a separate run.

## Independent application test

An independent Codex agent followed the converter's instructions on the prepared Windows venv tutorial. It read all 415 source segments, inspected all overview sheets and additional detailed frames, wrote the evidence/visual/output-map records, and generated a skill with two supporting references.

Observed results:

- Validator returned `verified_with_limits`: zero errors or scanner findings, three generated files, and 47 timestamp links.
- Three application exercises covered an incompatible-dependency handoff, intentionally shared packages with local-only export, and PowerShell/interpreter/deletion boundaries. Nine source conditions were checked. These were plan/artifact exercises; source commands and destructive operations were not executed.
- The evaluator retained the late-video `--system-site-packages` and `pip --local` qualifications and corrected caption-distorted commands using actual screen images.
- The evaluator identified excessive JSON overhead in source reads. Future unit sizing now budgets for row metadata/serialization overhead and emits compact read JSON; a regression test checks this behavior. Existing evidence IDs remain stable when resuming earlier runs.
- The evaluator also found repetitive status output and ambiguous detail-image filenames. Status now summarizes the visual ledger (`--details` retrieves it), frame commands return compact manifest/sheet references, and manifests report actual pixel dimensions separately from the requested maximum.

This was an independent agent's generation/application test, not a controlled benchmark against a no-skill baseline. Raw transcripts, images, generated tutorial output, and evaluator working notes remain outside the public repository.

## Limits of these checks

- Adaptive visuals are sampled, not every frame. Moving demonstrations can require denser manual follow-up.
- No ASR model was downloaded for the tests. Consent and import behavior are tested; a particular local speech model/hardware combination is not certified.
- Network restrictions and YouTube changes can still prevent retrieval. No paid proxy or extraction API is used.
- Unit ownership and output mapping do not prove faithful synthesis. That requires source review and application tests.
- Only the public converter is published. Test transcripts, video downloads, generated tutorial skills, and private evidence are excluded.
