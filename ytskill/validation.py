from __future__ import annotations

import re
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .common import Problem, atomic_json, confined, finite, read_json, tokens, video_id
from .runs import frame_catalog, integrity, source, validate_record


RULES = {
    "instruction_override": re.compile(r"\b(?:ignore|disregard)\s+(?:(?:all|any|the)\s+)?(?:previous|prior|system|developer)\s+(?:instructions?|prompts?|rules?|messages?)", re.I),
    "role_control": re.compile(r"<\s*/?system\b|<\|im_start\|>|\[INST\]|<\s*/?tool_call\b|^\s*(?:system|developer)\s*:", re.I | re.M),
    "authority_grant": re.compile(r"^\s*(?:allowed-tools|permissions|bypass_permissions|disable_sandbox)\s*:", re.I | re.M),
    "hidden_control": re.compile(r"[\u200b\u200e\u200f\u202a-\u202e\u2066-\u2069\U000e0000-\U000e007f]"),
    "possible_exfiltration": re.compile(r"(?:curl|wget|upload|send|https?://).{0,160}(?:api[_ -]?key|credential|\.env\b|secret)", re.I),
}
LINK = re.compile(r"!?\[[^\]]*\]\((<[^>]+>|[^)]+)\)")


def frontmatter(text: str) -> list[str]:
    # Generated frontmatter intentionally has only two single-line scalar keys.
    # No external YAML package is needed at run time.
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
    if not match:
        return ["SKILL.md needs YAML frontmatter with name and description."]
    values = {}
    errors = []
    for line in match[1].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.fullmatch(r"(name|description):\s*(.+)", line)
        if not item or item[1] in values:
            errors.append("Generated frontmatter supports exactly one name and one description scalar.")
            continue
        value = item[2].strip()
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                errors.append("Unclosed frontmatter quote.")
                continue
            if value[0] == '"':
                import json
                try:
                    value = json.loads(value)
                except ValueError:
                    errors.append("Use a JSON-compatible quoted description.")
                    continue
            else:
                value = value[1:-1].replace("''", "'")
        elif any(x in value for x in [": ", " #", "{", "}", "[", "]"]) or value in {"|", ">", "null", "true", "false"}:
            errors.append("Quote the frontmatter scalar to make YAML unambiguous.")
        values[item[1]] = value
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", values.get("name", "")) or len(values.get("name", "")) > 64:
        errors.append("Skill name must be a lowercase hyphenated slug of at most 64 characters.")
    if not values.get("description") or len(values.get("description", "")) > 1024:
        errors.append("Description must contain 1–1024 characters.")
    return errors


def scan(root: Path) -> tuple[list[dict], list[str], list[Path]]:
    findings, errors, files = [], [], []
    if root.is_symlink():
        return [], ["Skill root must be a real directory."], []
    total = 0
    candidates = []
    for base, dirs, names in os.walk(root, followlinks=False):
        for name in dirs:
            if (Path(base) / name).is_symlink():
                errors.append("Symlinks are not supported in generated artifacts.")
        candidates.extend(Path(base) / name for name in names)
    for path in sorted(candidates):
        if path.is_symlink():
            errors.append("Symlinks are not supported in generated artifacts.")
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".txt", ".json", ".yaml", ".yml"}:
            errors.append(f"Unexpected generated artifact type: {path.relative_to(root)}. Generated code belongs in quoted examples, not executable files.")
            continue
        if path.stat().st_size > 2_000_000:
            errors.append(f"Generated file exceeds scan limit: {path.relative_to(root)}")
            continue
        total += path.stat().st_size
        if total > 20_000_000 or len(files) >= 1000:
            errors.append("Generated artifact exceeds aggregate scan limits.")
            break
        files.append(path)
        text = path.read_text(encoding="utf-8-sig")
        for rule, pattern in RULES.items():
            for match in pattern.finditer(text):
                findings.append({"file": path.relative_to(root).as_posix(), "line": text.count("\n", 0, match.start()) + 1, "rule": rule})
    return findings, errors, files


def anchors(text: str) -> set[str]:
    found, counts, inside = set(), {}, False
    for line in text.splitlines():
        if re.match(r"\s*(`{3,}|~{3,})", line):
            inside = not inside
        if inside:
            continue
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)(?:\s+#+)?$", line)
        if match:
            heading = re.sub(r"[^\w\s-]", "", match[1].strip().lower())
            slug = re.sub(r"\s", "-", heading)
            number = counts.get(slug, 0)
            counts[slug] = number + 1
            found.add(slug if not number else f"{slug}-{number}")
        found.update(re.findall(r'<[^>]+\b(?:id|name)=["\']([^"\']+)["\']', line))
    return found


def validate(directory: Path, output: Path, *, accept_findings: Path | None = None) -> dict:
    run, transcript = source(directory)
    if output.is_symlink():
        raise Problem("unsafe_path", "Generated output must be a real directory, not a symlink.")
    output = output.resolve()
    errors, limitations = integrity(run, transcript), []
    master = output / "SKILL.md"
    if not master.is_file():
        errors.append("Generated SKILL.md is missing.")
    else:
        errors.extend(frontmatter(master.read_text(encoding="utf-8-sig")))
        if tokens(master.read_text(encoding="utf-8-sig")) > 4000:
            limitations.append("Entrypoint exceeds 4,000 estimated tokens; move details into references.")
    records = {}
    extracted_frames = frame_catalog(directory, run)
    reviewed_frames = {f for r in run["visuals"]["reviews"] if r["level"] in {"sampled", "close"} for f in r.get("frame_files", [])}
    for unit in run["units"]:
        path = directory / "evidence" / f"{unit['id']}.json"
        if not path.is_file():
            errors.append(f"Unprocessed unit: {unit['id']}")
            continue
        record = read_json(path)
        records[unit["id"]] = record
        errors.extend(f"{unit['id']}: {e}" for e in validate_record(run, transcript, record, frames=extracted_frames))
        for item in record.get("evidence", []):
            for frame in item.get("source_frames", []):
                if isinstance(frame, dict) and frame.get("file") not in reviewed_frames:
                    errors.append(f"{unit['id']}: Cited visual evidence is absent from the inspected-frame ledger.")
        if record.get("disposition") == "unresolved" or record.get("unresolved"):
            errors.append(f"Unresolved source evidence: {unit['id']}")
    mapping_file = directory / "output-map.json"
    mapping = read_json(mapping_file) if mapping_file.exists() else {}
    if not isinstance(mapping, dict):
        mapping = {}
    if set(mapping) != set(u["id"] for u in run["units"]):
        errors.append("output-map.json must account for every unit exactly once.")
    for unit_id, record in records.items():
        entry = mapping.get(unit_id, {})
        if not isinstance(entry, dict) or entry.get("disposition") != record.get("disposition"):
            errors.append(f"Output disposition mismatch: {unit_id}")
            continue
        targets = entry.get("files", [])
        if record["disposition"] == "incorporated" and not targets:
            errors.append(f"Incorporated unit has no output references: {unit_id}")
        for relative in targets:
            try:
                confined(output, relative.split("#")[0], exists=True)
            except Problem as exc:
                errors.append(f"{unit_id}: {exc}")
        if record["disposition"] == "redundant":
            covering = entry.get("covered_by")
            if covering == unit_id or covering not in records or records[covering].get("disposition") != "incorporated":
                errors.append(f"Redundant unit must name a distinct incorporated unit: {unit_id}")
    for gap in run["gaps"]:
        if gap["status"] == "unresolved":
            errors.append(f"Unresolved caption gap: {gap['id']}")
    visual = run["visuals"]
    if run.get("config", {}).get("source_mode") == "visual_only":
        limitations.append("Visual-only source: spoken/audio content was not transcribed or verified. The skill covers inspected on-screen teaching only.")
        if visual["capability"] != "available":
            errors.append("Visual-only processing requires actual image inspection.")
    if visual["capability"] == "unknown":
        errors.append("Visual capability and review coverage have not been recorded.")
    elif visual["capability"] == "unavailable":
        limitations.append(visual.get("limitation", "Visual contents were not inspected."))
    else:
        intervals = sorted(visual["reviews"], key=lambda x: x["start"])
        cursor = 0
        for item in intervals:
            if item["level"] == "unresolved":
                errors.append("Unresolved visual review interval.")
            if item["start"] > cursor + 1:
                errors.append("Visual review ledger has an unaccounted interval.")
            cursor = max(cursor, item["end"])
        if cursor < run["metadata"]["duration"] - 1:
            errors.append("Visual review ledger does not span the recording.")
        limitations.append("Visual review is adaptive sampling, not exhaustive frame-by-frame coverage.")
    if run["metadata"].get("duration_inferred"):
        errors.append("Full duration is inferred from captions. Supply verified metadata before claiming completed coverage.")
    findings, scan_errors, files = scan(output)
    errors.extend(scan_errors)
    accepted = []
    if accept_findings:
        accepted = read_json(accept_findings)
        if not isinstance(accepted, list) or any(not x.get("reason") for x in accepted):
            raise Problem("invalid_acceptance", "Accepted findings need file, line, rule, and a human review reason.")
    outstanding = [f for f in findings if not any(all(a.get(k) == f[k] for k in ["file", "line", "rule"]) for a in accepted)]
    if outstanding:
        errors.append("Suspicious generated instructions require human review. Findings identify locations without repeating source payloads.")
    timestamp_links = 0
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        content = path.read_text(encoding="utf-8-sig")
        for match in LINK.finditer(content):
            href = match[1].strip().strip("<>")
            parsed = urlparse(href)
            if parsed.scheme in {"http", "https"}:
                if (parsed.hostname or "").endswith("youtube.com") or parsed.hostname == "youtu.be":
                    try:
                        if video_id(href) != run["video_id"]:
                            errors.append("Generated source link points at another video.")
                            continue
                        values = parse_qs(parsed.query)
                        stamp = values.get("t", values.get("start", []))
                        if stamp:
                            value = stamp[0].removesuffix("s")
                            time = finite(value)
                            if time > run["metadata"]["duration"]:
                                errors.append("Generated timestamp link exceeds video duration.")
                            else:
                                timestamp_links += 1
                    except Problem:
                        errors.append("Invalid source timestamp or video URL.")
                continue
            if parsed.scheme:
                errors.append("Generated links must use relative files or HTTP(S).")
                continue
            candidate = path if not parsed.path else (path.parent / unquote(parsed.path)).resolve()
            try:
                if parsed.path:
                    confined(path.parent, unquote(parsed.path), exists=True)
            except Problem:
                # Sibling references may legitimately use ../ but must remain
                # within the generated skill root.
                candidate = (path.parent / unquote(parsed.path)).resolve()
                if not candidate.is_relative_to(output) or not candidate.is_file():
                    errors.append(f"Broken or escaping file link in {path.relative_to(output)}")
                    continue
            if parsed.fragment and candidate.is_file() and candidate.suffix.lower() == ".md":
                if unquote(parsed.fragment) not in anchors(candidate.read_text(encoding="utf-8-sig")):
                    errors.append(f"Broken heading anchor in {path.relative_to(output)}")
    if not timestamp_links:
        errors.append("Generated skill needs timestamped source links.")
    report = {"schema_version": 1, "video_id": run["video_id"], "run_identity": run["identity"], "status": "incomplete" if errors else "verified_with_limits", "errors": errors, "limitations": limitations, "findings": findings, "unaccepted_findings": outstanding, "units": len(run["units"]), "scanned_files": len(files), "timestamp_links": timestamp_links,
              "meaning": "Structural/coverage checks plus advisory scan; not proof of source fidelity or task performance."}
    atomic_json(directory / "validation.json", report)
    run["phase"] = report["status"]
    atomic_json(directory / "run.json", run)
    return report
