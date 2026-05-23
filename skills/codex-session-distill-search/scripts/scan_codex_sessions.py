#!/usr/bin/env python3
"""Build safe Codex session summaries for broad activity review."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan local Codex session logs and emit safe summary candidates."
    )
    parser.add_argument(
        "--codex-dir",
        default=os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"),
        help="Codex home directory, default: ${CODEX_HOME:-~/.codex}",
    )
    parser.add_argument("--date", help="Local date YYYY-MM-DD to scan.")
    parser.add_argument("--since", help="Start datetime, ISO-like local time.")
    parser.add_argument("--until", help="End datetime, ISO-like local time.")
    parser.add_argument(
        "--days",
        type=int,
        help="Scan the last N days ending now. Ignored if --date or --since is set.",
    )
    parser.add_argument("--limit", type=int, default=80, help="Max sessions to emit.")
    parser.add_argument("--chars", type=int, default=220, help="Max snippet length.")
    parser.add_argument("--compact", action="store_true", help="Emit one line per session.")
    parser.add_argument("--jsonl", action="store_true", help="Emit JSONL records.")
    return parser.parse_args()


def local_tz() -> timezone:
    return datetime.now().astimezone().tzinfo or timezone.utc


def parse_dt(value: str, tz: timezone) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        return datetime.fromisoformat(normalized[:-1] + "+00:00").astimezone(tz)
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def resolve_range(args: argparse.Namespace) -> tuple[datetime, datetime]:
    tz = local_tz()
    if args.date:
        day = datetime.fromisoformat(args.date).replace(tzinfo=tz)
        return day, day + timedelta(days=1)
    if args.since:
        since = parse_dt(args.since, tz)
        until = parse_dt(args.until, tz) if args.until else datetime.now(tz)
        return since, until
    days = args.days if args.days and args.days > 0 else 1
    until = datetime.now(tz)
    return until - timedelta(days=days), until


def load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                yield value


def parse_event_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value[:-1] + "+00:00")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=local_tz())
        return parsed
    except ValueError:
        return None


def shorten(text: str, limit: int) -> str:
    clean = " ".join(text.replace("\x00", "").split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)] + "..."


def text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict):
            text = item.get("text") or item.get("output_text")
            if isinstance(text, str):
                parts.append(text)
    return " ".join(parts)


def is_low_signal_user_text(text: str) -> bool:
    stripped = text.strip()
    return (
        stripped.startswith("# AGENTS.md instructions for ")
        or stripped.startswith("<skill>")
        or stripped.startswith("<INSTRUCTIONS>")
    )


def session_logs(codex_dir: Path) -> list[Path]:
    roots = [codex_dir / "sessions", codex_dir / "archived_sessions"]
    logs: list[Path] = []
    for root in roots:
        if root.exists():
            logs.extend(root.rglob("rollout-*.jsonl"))
    return sorted(set(logs), key=lambda p: str(p))


def load_index_names(codex_dir: Path) -> dict[str, str]:
    index = codex_dir / "session_index.jsonl"
    names: dict[str, str] = {}
    if not index.exists():
        return names
    for obj in load_jsonl(index):
        raw = json.dumps(obj, ensure_ascii=False)
        thread_id = obj.get("id") or obj.get("thread_id") or obj.get("conversation_id")
        name = obj.get("thread_name") or obj.get("title")
        if isinstance(thread_id, str) and isinstance(name, str) and name.strip():
            names[thread_id] = name.strip()
        elif isinstance(name, str):
            for part in raw.split('"'):
                if len(part) == 36 and part.count("-") == 4:
                    names[part] = name.strip()
    return names


def summarize_log(path: Path, names: dict[str, str], chars: int) -> dict[str, Any] | None:
    meta: dict[str, Any] = {}
    event_times: list[datetime] = []
    users: list[str] = []
    assistants: list[str] = []
    commands: list[str] = []
    markers: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()

    for obj in load_jsonl(path):
        event_type = str(obj.get("type") or "")
        if event_type:
            event_counts[event_type] += 1
        timestamp = parse_event_time(obj.get("timestamp"))
        if timestamp:
            event_times.append(timestamp)
        if event_type in {"turn_aborted", "patch_apply_end", "task_complete"}:
            markers[event_type] += 1

        payload = obj.get("payload")
        if event_type == "session_meta" and isinstance(payload, dict):
            meta.update(payload)
            meta_time = parse_event_time(payload.get("timestamp"))
            if meta_time:
                event_times.append(meta_time)

        if event_type == "response_item" and isinstance(payload, dict):
            payload_type = payload.get("type")
            if payload_type == "message":
                role = payload.get("role")
                text = shorten(text_from_content(payload.get("content")), chars)
                if role == "user" and text:
                    if not is_low_signal_user_text(text):
                        users.append(text)
                elif role == "assistant" and text:
                    assistants.append(text)
            elif payload_type == "function_call":
                name = str(payload.get("name") or "")
                if name == "exec_command":
                    cmd = ""
                    args = payload.get("arguments")
                    if isinstance(args, str):
                        try:
                            parsed = json.loads(args)
                        except json.JSONDecodeError:
                            parsed = {}
                        if isinstance(parsed, dict):
                            cmd = str(parsed.get("cmd") or "")
                    if cmd:
                        commands.append(shorten(cmd, chars))

    if not meta and not event_times and not users and not assistants:
        return None

    thread_id = str(meta.get("id") or path.stem.split("-")[-1])
    start = min(event_times).astimezone(local_tz()).isoformat() if event_times else ""
    end = max(event_times).astimezone(local_tz()).isoformat() if event_times else ""
    return {
        "thread_id": thread_id,
        "thread_name": names.get(thread_id, ""),
        "path": str(path),
        "start": start,
        "end": end,
        "cwd": meta.get("cwd", ""),
        "originator": meta.get("originator", ""),
        "source": meta.get("source", ""),
        "model": meta.get("model", ""),
        "user_messages": users[:4],
        "assistant_messages": assistants[-3:],
        "commands": commands[:6],
        "message_count": len(users) + len(assistants),
        "command_count": len(commands),
        "markers": dict(markers),
        "event_counts": dict(event_counts),
    }


def in_range(record: dict[str, Any], since: datetime, until: datetime) -> bool:
    times: list[datetime] = []
    for key in ("start", "end"):
        parsed = parse_event_time(record.get(key))
        if parsed:
            times.append(parsed.astimezone(local_tz()))
    if not times:
        return False
    return max(times) >= since and min(times) < until


def print_markdown(records: list[dict[str, Any]], since: datetime, until: datetime) -> None:
    by_cwd: dict[str, int] = defaultdict(int)
    for record in records:
        by_cwd[str(record.get("cwd") or "(unknown cwd)")] += 1

    print("# Codex session activity candidates")
    print(f"- range: {since.isoformat()} -> {until.isoformat()}")
    print(f"- sessions: {len(records)}")
    print("## cwd distribution")
    for cwd, count in sorted(by_cwd.items(), key=lambda item: (-item[1], item[0]))[:20]:
        print(f"- {count}\t{cwd}")

    print("## sessions")
    for record in records:
        print(f"### {record['thread_id']}")
        for key in ("thread_name", "start", "end", "cwd", "model", "path"):
            value = record.get(key)
            if value:
                print(f"- {key}: {value}")
        if record.get("markers"):
            print(f"- markers: {json.dumps(record['markers'], ensure_ascii=False)}")
        print("- user:")
        for text in record.get("user_messages", []):
            print(f"  - {text}")
        print("- assistant:")
        for text in record.get("assistant_messages", []):
            print(f"  - {text}")
        if record.get("commands"):
            print("- commands:")
            for cmd in record["commands"]:
                print(f"  - {cmd}")


def print_compact(records: list[dict[str, Any]], since: datetime, until: datetime) -> None:
    print(f"range={since.isoformat()}..{until.isoformat()} sessions={len(records)}")
    for record in records:
        topic_parts = []
        if record.get("thread_name"):
            topic_parts.append(str(record["thread_name"]))
        topic_parts.extend(str(item) for item in record.get("user_messages", [])[:2])
        topic = shorten(" / ".join(topic_parts), 260)
        status = shorten(" / ".join(str(item) for item in record.get("assistant_messages", [])[-2:]), 260)
        markers = json.dumps(record.get("markers") or {}, ensure_ascii=False)
        print(
            " | ".join(
                [
                    str(record.get("thread_id") or ""),
                    str(record.get("cwd") or ""),
                    topic,
                    status,
                    f"markers={markers}",
                    f"path={record.get('path') or ''}",
                ]
            )
        )


def main() -> int:
    args = parse_args()
    since, until = resolve_range(args)
    codex_dir = Path(args.codex_dir).expanduser()
    names = load_index_names(codex_dir)
    records: list[dict[str, Any]] = []

    for log in session_logs(codex_dir):
        record = summarize_log(log, names, args.chars)
        if record and in_range(record, since, until):
            records.append(record)

    records.sort(key=lambda item: str(item.get("end") or ""), reverse=True)
    records = records[: max(1, args.limit)]

    if args.jsonl:
        for record in records:
            print(json.dumps(record, ensure_ascii=False))
    elif args.compact:
        print_compact(records, since, until)
    else:
        print_markdown(records, since, until)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
