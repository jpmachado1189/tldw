# Optional free local transcription

Use only after the user explicitly agrees to local transcription. A lack of captions does not mean yt-dlp itself can generate them. No transcript is preferable to an invented one.

1. Explain the actual failure: captions absent, unusable, or retrieval blocked. Local transcription also requires accessible audio; it will not solve a video access restriction by itself.
2. Offer free local transcription, mentioning a possible model download and processing time. If declined, record `consent --choice declined` and retain the run. Do not install a model.
3. If agreed, record:

```text
PYTHON SKILL_ROOT/scripts/youtube_to_skill.py consent --run-dir RUN_DIRECTORY --choice granted
PYTHON SKILL_ROOT/scripts/youtube_to_skill.py audio --run-dir RUN_DIRECTORY
```

4. The host examines existing tools and available compute, then selects a suitable free local transcriber, such as [faster-whisper](https://github.com/SYSTRAN/faster-whisper) or [whisper.cpp](https://github.com/ggml-org/whisper.cpp). Reuse existing installations; otherwise arrange an isolated setup. Choose model and execution mode for this environment rather than prescribing a GPU, CUDA installation, or model download to every user. No paid API fallback is authorized.
5. Transcribe in resumable pieces if necessary. Preserve absolute video timestamps, recording chunk offsets and overlap reconciliation. Review suspicious repetition, nonspeech hallucinations, names, numbers, and language changes. Do not translate the spoken content implicitly.
6. Save VTT, SRT, or a JSON list of `{start, end, text}` segments, then import:

```text
PYTHON SKILL_ROOT/scripts/youtube_to_skill.py prepare YOUTUBE_URL --work-dir WORK_DIRECTORY --transcript TIMED_TRANSCRIPT --metadata VIDEO_METADATA --transcription-method TOOL_AND_MODEL --consent-run CONSENT_RUN_DIRECTORY
```

`VIDEO_METADATA` must contain the requested video's ID and verified duration; the prior run's metadata can be saved to a separate JSON file and reused. The helper checks consent against the same video. This creates an identity for the recovered transcript. Re-run the evidence workflow on the new source; do not silently carry notes across changed timestamps.

Existing user-supplied captions do not require transcription consent. Import those without `--transcription-method`. Untimed prose can be useful supplementary context but cannot establish complete video coverage and is not accepted as the primary timed transcript.
