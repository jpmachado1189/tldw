# Evidence, checkpoints, and output mapping

Every CLI command emits JSON on stdout. Exit 0 means the command succeeded; exit 2 means invalid input, a failed stage, awaiting source, or incomplete validation. Diagnostic setup output goes to stderr. Do not treat a nonzero prepare result as a lost run: it can include a usable `run_dir`.

The run contains versioned `run.json`, an immutable normalized `transcript.json`, preserved `original.json`, per-unit evidence, optional media/visuals, the output map, and validation results. Source hash checks prevent silent in-place changes. Re-preparing changed source/configuration creates a separate run; identical input reuses existing progress. `resume` returns status and the next pending unit; it does not silently rerun network calls.

## Evidence record

Use the exact segment IDs from `read --unit`. Context-only segments do not belong to this unit. Evidence timestamps must lie inside the unit and overlap cited source segments. Save a JSON file like:

```json
{
  "unit_id": "u0001",
  "disposition": "incorporated",
  "reason": "Contains the selection procedure; the opening greeting adds no instruction.",
  "segment_ids": ["s000001", "s000002"],
  "evidence": [
    {
      "claim": "State the actual source-supported method here.",
      "kind": "procedure",
      "start": 12.0,
      "end": 25.0,
      "source_segment_ids": ["s000002"],
      "inputs": ["Required source-supported input"],
      "steps": ["Source-supported step"],
      "decision_criteria": ["Condition and action"],
      "expected_result": "Observable outcome",
      "qualifications": ["When it does not apply"],
      "speaker": null,
      "visual_dependencies": []
    }
  ],
  "unresolved": []
}
```

The sample is a schema illustration, not video evidence. `claim`, timestamps, and `source_segment_ids` are required on each evidence item; other fields are added when the source supports them. Keep numerical thresholds, exact names, corrections, and worked examples. Do not fill empty fields with invented knowledge.

Disposition values: `incorporated`, `redundant`, `non_instructional`, `unresolved`. Redundant and non-instructional records still list all owned segments and a meaningful reason. An unresolved list blocks a completed result even if other parts of the unit are useful. Updating a record atomically replaces that unit's previous notes; read them first so corrections do not erase useful evidence.

Long single captions may be split with `parent_id` and `timing_precision: parent_caption`. Their timestamps refer to the original cue, not invented word-level alignment. Caption gap detection is heuristic; all gaps over 30 seconds need review, not an assumption that speech was missing.

## Review ledger

Submit with `review --run-dir RUN_DIRECTORY --file REVIEW_JSON`. Gap updates are merged; a supplied visual ledger replaces the existing visual ledger, so include prior reviews when extending it.

```json
{
  "gaps": [{"id": "g0001", "status": "silence", "reason": "The inspected interval contains a silent setup screen."}],
  "visuals": {
    "capability": "available",
    "reviews": [{
      "start": 0,
      "end": 600,
      "level": "sampled",
      "notes": "Inspected overview sheets across this interval; expanded the demonstration at 120–150 seconds separately.",
      "frame_files": ["visuals/MEDIA_ID/frame-0000120000-960.jpg"]
    }]
  }
}
```

Gap states: `silence`, `non_instructional`, `recovered`, `unresolved`. To recover missing speech, prefer re-preparing a corrected transcript; record recovery only when the recovered instruction and its evidence were actually incorporated.

Visual levels: `sampled`, `close`, `unresolved`. Intervals may overlap and should account for the duration. `frame_files` refer to inspected frames, not merely extracted ones. For unavailable images:

```json
{"visuals":{"capability":"unavailable","limitation":"This host cannot inspect images; on-screen content is unverified.","reviews":[]}}
```

## Output map

Before final validation, submit a JSON object with exactly one entry per unit:

```json
{
  "u0001": {"disposition":"incorporated","files":["references/selection.md"]},
  "u0002": {"disposition":"redundant","covered_by":"u0001","files":[]},
  "u0003": {"disposition":"non_instructional","files":[]}
}
```

Each incorporated unit must map to real generated files. This acknowledges processing, not automatic proof that every claim survived synthesis. The host must audit the mapping against the actual generated text.

## Scanner findings

The validator scans every generated Markdown/text/JSON/YAML file, not just the root skill. It reports location and rule, never the matched payload. Legitimate security teaching can trigger it. Obtain human review rather than silently suppressing it. To record accepted findings, supply `--accept-findings ACCEPTANCE_JSON`, a list of `{ "file": "...", "line": 1, "rule": "...", "reason": "Human review decision and why" }` objects. Never generate acceptance on the user's behalf.

`verified_with_limits` means structural/coverage checks passed subject to recorded visual limits. It does not certify semantic fidelity, code correctness, or downstream task performance.
