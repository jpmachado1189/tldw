from __future__ import annotations

import html
import json
import re

from .common import Problem, finite, tokens


STAMP = r"(?:\d+:)?\d{2}:\d{2}[.,]\d{3}"
CAPTION_TAG = re.compile(r"<(?:/?(?:c(?:\.[\w.-]+)?|i|b|u|ruby|rt|lang|v|font)(?:\s+[^>]*)?|(?:\d+:)?\d{2}:\d{2}\.\d{3})>", re.I)


def seconds(stamp: str) -> float:
    parts = stamp.replace(",", ".").split(":")
    return sum(float(part) * 60 ** index for index, part in enumerate(reversed(parts)))


def parse(text: str, format: str) -> list[dict]:
    """Normalize timed JSON/JSON3/VTT/SRT, never manufacture timestamps for prose."""
    raw = []
    if format.lower() in {"json", "json3"}:
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise Problem("invalid_captions", "Caption JSON is malformed.") from exc
        if isinstance(data, dict) and "events" in data:
            for event in data["events"]:
                body = "".join(x.get("utf8", "") for x in event.get("segs", []))
                if body.strip():
                    start = finite(event.get("tStartMs", 0)) / 1000
                    duration = finite(event.get("dDurationMs", 0)) / 1000
                    raw.append({"start": start, "end": start + duration, "text": body})
        else:
            if isinstance(data, dict):
                data = data.get("segments", data.get("snippets", []))
            if not isinstance(data, list):
                raise Problem("invalid_captions", "Expected a list of timed segments.")
            for item in data:
                if not isinstance(item, dict):
                    raise Problem("invalid_captions", "Each caption must be an object.")
                start = finite(item.get("start"))
                end = finite(item["end"]) if "end" in item else start + finite(item.get("duration"))
                raw.append({"start": start, "end": end, "text": item.get("text", "")})
    elif format.lower() in {"vtt", "srt"}:
        lines = text.replace("\r\n", "\n").splitlines()
        for index, line in enumerate(lines):
            match = re.match(rf"\s*({STAMP})\s*-->\s*({STAMP})", line)
            if not match:
                continue
            body = []
            for next_line in lines[index + 1:]:
                if not next_line.strip():
                    break
                body.append(next_line)
            raw.append({"start": seconds(match[1]), "end": seconds(match[2]), "text": " ".join(body)})
    else:
        raise Problem("untimed_transcript", "Provide timestamped JSON, JSON3, VTT, or SRT. Plain prose cannot establish video coverage.")
    output = []
    for index, item in enumerate(raw):
        if not isinstance(item["text"], str):
            raise Problem("invalid_captions", "Caption text must be a string.")
        start, end = finite(item["start"]), finite(item["end"])
        if end < start:
            raise Problem("invalid_timestamp", "A caption ends before it starts.")
        body = html.unescape(CAPTION_TAG.sub("", item["text"]))
        body = re.sub(r"\s+", " ", body).strip()
        if body:
            output.append({"id": f"s{index + 1:06d}", "start": start, "end": end, "text": body})
    if not output:
        raise Problem("no_captions", "No usable timed caption text was found.")
    return sorted(output, key=lambda x: (x["start"], x["end"]))


def deduplicate(raw: list[dict]) -> list[dict]:
    """Only remove exact adjacent rolling prefixes during temporal overlap.

    Keep even fully duplicated segment IDs for auditable ownership. Repeated
    phrases at later times and partially matching wording remain untouched.
    """
    output = []
    previous = None
    for item in raw:
        current = dict(item)
        if previous and item["start"] < previous["end"]:
            before, after = previous["text"].split(), item["text"].split()
            overlap = 0
            for size in range(min(len(before), len(after)), 1, -1):
                if before[-size:] == after[:size]:
                    overlap = size
                    break
            if before == after:
                overlap = len(after)
            if overlap:
                current["text"] = " ".join(after[overlap:])
                current["rolling_prefix_from"] = previous["id"]
        output.append(current)
        previous = item
    return output


def split_segments(segments: list[dict], budget: int) -> list[dict]:
    """Split oversized cues without pretending their sub-text has precise timing."""
    out = []
    for segment in segments:
        if tokens(segment["text"]) <= budget:
            out.append(segment)
            continue
        text = segment["text"]
        pieces = []
        while text:
            high, low = len(text), 1
            while low < high:
                mid = (low + high + 1) // 2
                if tokens(text[:mid]) <= budget:
                    low = mid
                else:
                    high = mid - 1
            stop = low
            space = text.rfind(" ", 0, stop + 1)
            if space > stop // 2:
                stop = space
            pieces.append(text[:stop].strip())
            text = text[stop:].lstrip()
        for index, text in enumerate(pieces):
            out.append({**segment, "id": f"{segment['id']}-{index + 1:03d}", "parent_id": segment["id"], "text": text, "timing_precision": "parent_caption"})
    return out


def make_units(segments: list[dict], chapters: list[dict], budget=3000, overlap_budget=160):
    if not 200 <= budget <= 12000:
        raise Problem("invalid_budget", "Unit token target must be between 200 and 12000.")
    # Reserve space for each row's identity/timing/JSON overhead, not just words.
    # Otherwise a "3k token" unit of short captions can emit >10k tokens.
    segments = split_segments(segments, max(40, budget - 160))
    def cost(segment):
        return tokens(json.dumps(segment, ensure_ascii=False, separators=(",", ":"))) + tokens(segment["id"]) + 2
    boundaries = sorted(finite(c["start_time"]) for c in chapters if "start_time" in c)
    groups, current, size = [], [], 0
    for segment in segments:
        section_change = current and any(current[-1]["start"] < t <= segment["start"] for t in boundaries)
        weight = cost(segment)
        if current and (size + weight > budget or (section_change and size > budget // 4)):
            groups.append(current)
            current, size = [], 0
        current.append(segment)
        size += weight
    if current:
        groups.append(current)
    units = []
    for index, group in enumerate(groups):
        context, spent = [], 0
        if index:
            for item in reversed(groups[index - 1]):
                weight = cost(item)
                if spent + weight > overlap_budget:
                    break
                context.insert(0, item["id"])
                spent += weight
        units.append({"id": f"u{index + 1:04d}", "start": group[0]["start"], "end": max(x["end"] for x in group), "segment_ids": [x["id"] for x in group], "context_ids": context, "estimated_tokens": sum(cost(x) for x in group)})
    return segments, units


def gaps(segments: list[dict], duration: float, threshold=30) -> list[dict]:
    output, cursor = [], 0.0
    for segment in segments:
        if segment["start"] - cursor > threshold:
            output.append({"start": cursor, "end": segment["start"]})
        cursor = max(cursor, segment["end"])
    if duration - cursor > threshold:
        output.append({"start": cursor, "end": duration})
    return [{"id": f"g{index + 1:04d}", **item, "status": "unresolved", "reason": "Caption gap; silence versus missing teaching is unknown."} for index, item in enumerate(output)]
