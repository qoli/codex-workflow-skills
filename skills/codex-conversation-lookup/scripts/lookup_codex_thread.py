#!/usr/bin/env python3
"""Locate and summarize local Codex conversation logs by UUID."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find local Codex rollout logs and print a safe reading route."
    )
    parser.add_argument("uuid", help="Codex conversation/thread UUID")
    parser.add_argument(
        "--codex-dir",
        default=os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"),
        help="Codex home directory, default: ${CODEX_HOME:-~/.codex}",
    )
    parser.add_argument(
        "--message-limit",
        type=int,
        default=18,
        help="Maximum message timeline rows per log, default: 18",
    )
    parser.add_argument(
        "--chars",
        type=int,
        default=220,
        help="Maximum characters per text snippet, default: 220",
    )
    return parser.parse_args()


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


def shorten(value: str, limit: int) -> str:
    value = " ".join(value.replace("\x00", "").split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "..."


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


def find_index_matches(index_path: Path, uuid: str) -> list[dict[str, Any]]:
    if not index_path.exists():
        return []
    matches: list[dict[str, Any]] = []
    for obj in load_jsonl(index_path):
        raw = json.dumps(obj, ensure_ascii=False)
        if uuid in raw:
            matches.append(obj)
    return matches


def find_logs(codex_dir: Path, uuid: str) -> list[Path]:
    roots = [codex_dir / "sessions", codex_dir / "archived_sessions"]
    logs: list[Path] = []
    for root in roots:
        if root.exists():
            logs.extend(root.rglob(f"*{uuid}*.jsonl"))
    return sorted(set(logs), key=lambda p: str(p))


def find_shell_snapshots(codex_dir: Path, uuid: str) -> list[Path]:
    root = codex_dir / "shell_snapshots"
    if not root.exists():
        return []
    return sorted(root.glob(f"{uuid}.*.sh"), key=lambda p: str(p))


def summarize_log(path: Path, chars: int, message_limit: int) -> dict[str, Any]:
    meta: list[dict[str, Any]] = []
    messages: list[tuple[str, str, str]] = []
    commands: list[tuple[str, str]] = []
    event_counts: Counter[str] = Counter()
    markers: Counter[str] = Counter()

    for obj in load_jsonl(path):
        event_type = str(obj.get("type") or "")
        if event_type:
            event_counts[event_type] += 1
        if event_type in {"turn_aborted", "patch_apply_end", "task_complete"}:
            markers[event_type] += 1

        payload = obj.get("payload")
        if event_type == "session_meta" and isinstance(payload, dict):
            meta.append(payload)

        if event_type == "response_item" and isinstance(payload, dict):
            payload_type = payload.get("type")
            if payload_type == "message" and payload.get("role") in {"user", "assistant"}:
                text = shorten(text_from_content(payload.get("content")), chars)
                messages.append(
                    (str(obj.get("timestamp") or ""), str(payload.get("role")), text)
                )
            elif payload_type == "function_call":
                name = str(payload.get("name") or "")
                if name == "exec_command":
                    args = payload.get("arguments")
                    cmd = ""
                    if isinstance(args, str):
                        try:
                            parsed = json.loads(args)
                        except json.JSONDecodeError:
                            parsed = {}
                        if isinstance(parsed, dict):
                            cmd = str(parsed.get("cmd") or "")
                    commands.append(
                        (str(obj.get("timestamp") or ""), shorten(cmd, chars))
                    )

    return {
        "meta": meta,
        "messages": messages[:message_limit],
        "message_count": len(messages),
        "commands": commands[:message_limit],
        "command_count": len(commands),
        "event_counts": event_counts,
        "markers": markers,
    }


def print_index(matches: list[dict[str, Any]], chars: int) -> None:
    print("## Index matches")
    if not matches:
        print("- none")
        return
    for i, obj in enumerate(matches, 1):
        interesting = {
            key: obj.get(key)
            for key in [
                "id",
                "thread_id",
                "conversation_id",
                "title",
                "thread_name",
                "thread_name_updated",
                "updated_at",
                "timestamp",
                "cwd",
            ]
            if key in obj
        }
        if not interesting:
            print(f"- match {i}: {shorten(json.dumps(obj, ensure_ascii=False), chars)}")
        else:
            print(f"- match {i}: {json.dumps(interesting, ensure_ascii=False)}")


def print_log_summary(path: Path, summary: dict[str, Any]) -> None:
    print(f"## Log: {path}")
    metas = summary["meta"]
    if metas:
        print("### session_meta")
        for meta in metas:
            for key in [
                "id",
                "timestamp",
                "cwd",
                "originator",
                "cli_version",
                "source",
                "model",
            ]:
                if key in meta:
                    print(f"- {key}: {meta.get(key)}")
    else:
        print("### session_meta")
        print("- none found")

    markers = summary["markers"]
    if markers:
        print("### markers")
        for key, count in sorted(markers.items()):
            print(f"- {key}: {count}")

    print("### message timeline")
    messages = summary["messages"]
    if not messages:
        print("- none")
    for timestamp, role, text in messages:
        print(f"- {timestamp}\t{role}\t{text}")
    if summary["message_count"] > len(messages):
        print(f"- ... {summary['message_count'] - len(messages)} more message rows omitted")

    print("### exec commands")
    commands = summary["commands"]
    if not commands:
        print("- none")
    for timestamp, cmd in commands:
        print(f"- {timestamp}\t{cmd}")
    if summary["command_count"] > len(commands):
        print(f"- ... {summary['command_count'] - len(commands)} more command rows omitted")


def main() -> int:
    args = parse_args()
    uuid = args.uuid.strip()
    if not UUID_RE.match(uuid):
        raise SystemExit("error: UUID shape is invalid")

    codex_dir = Path(args.codex_dir).expanduser()
    print(f"# Codex conversation lookup: {uuid}")
    print(f"- codex_dir: {codex_dir}")

    index_matches = find_index_matches(codex_dir / "session_index.jsonl", uuid)
    logs = find_logs(codex_dir, uuid)
    snapshots = find_shell_snapshots(codex_dir, uuid)

    print_index(index_matches, args.chars)

    print("## Rollout logs")
    if not logs:
        print("- none")
    for log in logs:
        print(f"- {log}")

    print("## Shell snapshots")
    if not snapshots:
        print("- none")
    for snapshot in snapshots:
        print(f"- {snapshot}")

    for log in logs:
        print()
        print_log_summary(log, summarize_log(log, args.chars, args.message_limit))

    print()
    print("## Next reading route")
    print("- Confirm session_meta and cwd.")
    print("- Read user messages after any injected workspace instructions.")
    print("- Inspect assistant finals/commentary for delivered conclusions.")
    print("- For continuation, inspect aborted turns, patch events, commands, and snapshots only as needed.")
    print("- Summarize relevant context; do not paste raw private logs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
