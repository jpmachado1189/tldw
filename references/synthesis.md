# From teaching to usable skill

The output is an operational method with evidence. Chronological recaps alone are insufficient.

## Reconcile before writing

Read the saved unit evidence and build a task inventory: what can a practitioner accomplish using this video? Link inputs, prerequisites, choices, procedures, examples, and failure modes. Preserve corrections made later in the recording. Different speakers can disagree; describe their conditions or disagreement rather than inventing a consensus.

Do not assume a phrase is a named framework unless the source presents it that way. Do not convert motivational rhetoric into a quantitative guarantee. When the video lacks sufficient instruction to form an actionable skill, explain that and return a bounded reference or incomplete draft rather than manufacturing expertise.

## Root skill

Use frontmatter with exactly `name` and `description`; quote the description as a JSON-compatible string. Give it a lowercase hyphenated name reflecting the capability, not just the video title. The description should identify the task and situations where the skill applies.

The body should enable:

1. Recognizing when the method fits.
2. Gathering necessary inputs.
3. Following the working procedure.
4. Making the source's key decisions.
5. Checking the outcome and responding to failure.
6. Opening the correct detailed reference when needed.

Use compact Markdown and relative links. Avoid arbitrary fixed template sections when they would be empty. Detailed study material belongs in references. The root should instruct the agent to open the relevant method reference before applying details it does not contain.

## Evidence and examples

Use source links in the form `https://www.youtube.com/watch?v=VIDEO_ID&t=SECONDS`, with decimal or integer seconds. Put timestamps beside the supported method or example. Distinguish three things:

- **Source teaching:** faithfully extracted instructions and conditions.
- **Reconstructed example:** a compact, faithful reworking of an example the speaker demonstrates.
- **Agent-created adaptation/example:** new application, explicitly labeled, never attributed to the speaker.

Preserve exact code or numerical detail only when recovered clearly. Do not expand long verbatim passages or package a substitute transcript. The public converter's license does not confer rights to republish third-party video contents.

Record title, channel, original URL, duration, caption method/language, the timeline-to-topic index, and all capture limits in the generated source reference. Omit local file paths, signed URLs, account information, and raw source files.

## Application check

Construct a new scenario requiring the method: a choice between options, a filled template, a proposed procedure, or a diagnosis. Apply the generated skill using only its files. Compare against the original evidence. Look for missed prerequisites, ignored exceptions, wrong thresholds, or a failure to produce the intended result.

For dense material include an exception case and a case whose essential teaching occurs late in the video. For visual demonstrations include a required step visible on screen. Fix the skill if the application reveals a supported omission; do not patch it with invented details. Record this behavioral result separately from the deterministic validation report.
