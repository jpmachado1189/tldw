# Validation record

Validation dates: 2026-09-11 to 2026-09-12. Version: 0.2.1, named tldw. The converter is portable by design; the complete interactive workflow was verified first in Codex on Windows. Other harnesses require their own behavioral verification.

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

Local result: **73 tests passed**, Ruff passed, and the Codex skill-creator validator passed. Earlier checks also verified an editable package install and the helper's `bootstrap --visual` operation into a fresh isolated environment. No ASR model was installed.

Run `python -m pytest -q` and `python -m ruff check .` from the checkout. CI runs the offline suite on Windows, Ubuntu, and macOS with Python 3.10 and 3.12. All six combinations passed for the 0.2.0 implementation in [this CI run](https://github.com/jpmachado1189/tldw/actions/runs/34655871617). CI status is separate from behavioral harness support. The release ZIP was also extracted into a separate workspace, where the helper's `doctor` command succeeded without relying on the development checkout or `PYTHONPATH`.

## Live extraction checks

Raw test material remains local, outside this repository.

Version 0.2.0 adds tested visual-only timeline units, direct inspected-frame evidence without fake caption anchors, registered timestamp validation, and a completion gate requiring cited frames to appear in the visual review ledger. Synthetic silent-video tests use actual FFmpeg media and verify that audio limits remain explicit. Other tests exercise five-hour visual timeline coverage, idempotent supplemental units, clip-local to source-absolute timestamps, cached section downloads, invalid/empty sections, and timeout cleanup of utility child processes.

The full course run exposed an advisory scanner false positive: it matched `send` inside `sender` and `secret` inside `secretary` in a warning about deceptive identities. Version 0.2.1 recognizes words and underscore-delimited credential variables. Four benign-language cases and seven actual secret-transfer cases now check this behavior, including API keys, credentials, `.env`, curl/wget, and environment-variable names. The source-derived warning was retained without an acceptance override or rewriting it to evade the scanner.

A live ten-second section from the Nick Saraev course at 03:24:55 produced a 1,351,109-byte H.264 clip and two readable 1920x1080 frames at the correct absolute times. The initial HLS section had returned an empty MP4 despite a zero exit code; detail extraction now prefers direct HTTP formats, validates decoded frames, and has a cached-full-file fallback. In the later fresh course run, the initial 40 detail requests succeeded through 34 section downloads (22,420,777 bytes combined) and six requests served from one reusable full detail file (493,148,674 bytes). Both successful section retrieval and recovery through the full-file cache have therefore been exercised live.

| Source | Observed result |
|---|---|
| [Corey Schafer: Windows venv tutorial](https://www.youtube.com/watch?v=APOPm01BVrk) | Retrieved a 17:09 tutorial's captions, extracted 35 timestamped preview frames and three contact sheets, with no failed frame requests in the overview. |
| [Programming with Mosh: Python course](https://www.youtube.com/watch?v=_uQrJ0TkZlc) | Verified duration 6:14:07. The selected manual captions left a 4,143-second tail gap. Comparing the automatic original-English track recovered coverage through the end, with no remaining detected gaps over 30 seconds. Normalized 9,993 caption segments; ownership check passed. |
| [Nick Saraev: Cold Email Copywriting & Outreach](https://www.youtube.com/watch?v=uSTGNHGFOAo) | Verified duration 3:59:11. Retrieved original-English automatic captions: 8,029 segments, 51,987 words, 84 bounded reading units, all 29 chapters represented, no detected gaps over 30 seconds, and no missing or multiply owned segments. Largest serialized source-read estimate: 3,035 tokens. Extracted 597 adaptive overview frames on 50 contact sheets without failed requests, through the final second. |

The long-course test verifies retrieval, gap handling, and bounded source preparation. It is **not** a claim that the entire six-hour course was synthesized and behaviorally evaluated. Gap detection is heuristic; zero detected gaps does not establish word-perfect transcription.

The initial Nick Saraev exploration read five complete units distributed across the recording, plus a short boundary passage. It inspected five of the 50 overview sheets, a coarse eight-frame contact sheet, and five closer samples of a late follow-up diagram. The incomplete-output gate correctly rejected the remaining 79 units and two unresolved example/procedure boundaries. That initial exploration tested retrieval, visual access, evidence, and resume; it did not complete a generated skill.

The live repeat-run test exposed a resume defect: YouTube alternated `en-US` and `en` in original-language metadata despite returning identical captions. Version 0.1.1 normalizes these descriptive labels for identity comparison and recognizes older equivalent checkpoints. The live retest preserved all five evidence records byte-for-byte and resumed at the first pending unit. Three additional regression tests cover legacy-checkpoint reuse, conflicting progress, and preservation of distinct selected caption tracks/requested languages; changed source text still produces a separate run.

## Full Nick Saraev course conversion

A fresh Codex agent received the converter instructions and the course URL, without the earlier exploration's evidence or intended answers. It completed the 3:59:11 source-to-skill workflow using free caption/media utilities and the host's reasoning/image capabilities. No transcription model or paid extraction API was used.

- All 8,029 caption segments and 84 processing units were read and recorded: 82 units incorporated and two non-instructional units accounted for.
- The run saved 213 timestamped teaching records, including 46 supported by inspected source images.
- Visual review covered all 50 overview contact sheets (597 preview frames), 45 individually opened high-resolution stills, and a five-frame sequence sheet with one expanded frame. The ledger contains 646 distinct reviewed frame files. This is adaptive sampling, not every frame.
- The final 45 detail requests used 34 short section downloads and 11 requests served from one reusable full detail cache. There were no unresolved frame requests in the completed manifests.
- The generated skill has 11 Markdown files: a roughly 2,607-token entry point, nine task/source references, and a working-brief template. It preserves 26 catalog offer patterns and nine live rewrite comparisons without bundling raw captions or video.
- Parent verification and the skill-creator validator passed. Final conversion validation returned `verified_with_limits`: all units mapped, 164 timestamp links, zero errors, and zero scanner findings. No finding acceptance override was used.

The visual path corrected concrete errors: two templates show 15-minute calls where automatic captions said 50; the editing example is 60 seconds in both before/after images; and the thumbnail example shows 7–8% rather than 78%. It also recovered unspoken offer rows and an awareness-only message's no-CTA exception. The parent separately inspected both 15-minute template frames.

The conversion agent then used the generated files for a bounded fictional application exercise and compared its outputs with source evidence afterwards. It produced sample-edit outreach, an alternative concept and a follow-up, and checked 11 conditions: appropriate commitment, supported proof, the visible Drive-sharing input, actual recipient effort, truthful context, deadline and CTA exceptions, a near-miss guarantee, late name normalization, sparse-data uncertainty, and the account-purchase boundary. All 11 checks passed. This was a same-agent application exercise, not a blinded evaluator or a live campaign. A fresh user-led task remains a separate test of transfer.

The generated skill, application artifacts, captions, media, and detailed working evidence remain local and are not part of this public repository.

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
