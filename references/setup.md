# Portable setup

The converter's Python orchestration uses only the standard library. It can be run directly from its installation. Python 3.10+ is the baseline; the host locates an existing interpreter, including its bundled runtime, or arranges an isolated local runtime within its permissions. Do not hardcode a developer's Windows path into instructions or artifacts.

Prefer an already working environment. Otherwise:

```text
PYTHON SKILL_ROOT/scripts/tldw.py bootstrap --env-dir LOCAL_ENV_DIRECTORY --visual
```

Use the returned Python executable for subsequent commands. The helper installs `yt-dlp[default]`, `youtube-transcript-api`, Pillow, and imageio-ffmpeg in that environment. It does not install ASR models. Pillow builds contact sheets; imageio-ffmpeg supplies a platform wheel with an FFmpeg executable when no system FFmpeg exists. Availability varies by platform; on unsupported architectures the host should obtain FFmpeg through the platform's supported distribution.

YouTube challenge solving also needs a supported JavaScript runtime. Reuse Node 22+ or supported Deno. If neither exists, let the host arrange one locally; no global shell profile edits are required. `yt-dlp[default]` includes its matching EJS package. When repairing extraction, upgrade yt-dlp and its default dependencies together in the isolated environment, then retry once. Do not reinstall in a loop or add paid proxies.

Environment overrides (optional):

| Variable | Value |
|---|---|
| `YTS_YTDLP` | Path to an existing yt-dlp executable |
| `YTS_JS_RUNTIME` | yt-dlp runtime specification, e.g. `node:/absolute/path/to/node` |
| `YTS_FFMPEG` | Path to an existing FFmpeg executable |

`doctor` reports utility availability; a real retrieval verifies interoperability. Utilities are invoked with argument arrays, not source-derived shell text. yt-dlp ignores ambient user config and plugins so unrelated download settings do not alter the workflow. Cookies are not collected or exported automatically. In this release, restricted material should be supplied as an accessible local file/transcript rather than importing browser credentials.

Public sources:
- [yt-dlp installation](https://github.com/yt-dlp/yt-dlp/wiki/Installation)
- [JavaScript/EJS requirements](https://github.com/yt-dlp/yt-dlp/wiki/EJS)
- [Caption fallback and access limits](https://github.com/jdepoix/youtube-transcript-api)
- [FFmpeg Python wheels](https://github.com/imageio/imageio-ffmpeg)

Extraction software is free; downloading and processing still use bandwidth, disk space, and compute. The current host's synthesis/image interpretation uses its normal allowance. No separate paid extraction account is used.
