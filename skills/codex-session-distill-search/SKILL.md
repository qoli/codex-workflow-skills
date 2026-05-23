---
name: codex-session-distill-search
description: Broad local Codex session search and safe activity summarization with distill. Use when the user asks what they did today, yesterday, recently, this week, or during a time range; asks to summarize Codex work history without providing a UUID; says things like "看看昨天做什麼", "今天做了什麼", "最近我在忙什麼", "整理一下這幾天的 Codex 對話"; or wants a dominant workstream summary across many local Codex Desktop/CLI sessions. For exact UUID recovery, hand off to codex-conversation-lookup instead.
---

# Codex Session Distill Search

## Purpose

Summarize local Codex session activity across a date or time range without exposing raw private transcripts. Use `distill` with oMLX `gemma-4-e4b-it` at `http://127.0.0.1:8001/v1` to compress broad session timelines, then read only the few source logs needed to verify the summary. The exact oMLX API model id is `gemma-4-e4b-it-8bit`.

This skill complements `codex-conversation-lookup`: use this skill for broad "what did I do" searches; use `codex-conversation-lookup` for a specific UUID.

## Workflow

1. Interpret the user's time range. If they state a custom day boundary, use it. If they say "yesterday" or "today" and no boundary is stated, use the local timezone and mention the concrete date range.
2. Run the helper to build safe session candidates:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/codex-session-distill-search/scripts/scan_codex_sessions.py" --date YYYY-MM-DD
```

3. Pipe compact broad output through `distill` with oMLX `gemma-4-e4b-it` and an explicit English question:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/codex-session-distill-search/scripts/scan_codex_sessions.py" --date YYYY-MM-DD --compact \
  | distill --host http://127.0.0.1:8001/v1 --model gemma-4-e4b-it-8bit --api-key "${OMLX_API_KEY:-1234}" \
      "Pick the dominant workstreams. Return max 8 rows: thread_id | cwd | topic | status_or_risk. Exclude the current recap/test task if present. Do not quote private transcript text."
```

4. Treat the distilled result as an index. If `distill` returns only headers, schema text, or "insufficient information", fall back to the helper output and narrow `--limit` or the time range. Do not use the built-in distill 1.7B local model as the default for this broad session-summary task; it is faster but produced weak headers-only summaries in testing.
5. Re-open only the top source logs needed to verify cwd, time, completion state, aborted turns, commands, and patches.
6. Answer with a synthesized work recap in the user's language, not a thread-title dump.

## Helper Options

Use one of:

```bash
scan_codex_sessions.py --date 2026-05-23
scan_codex_sessions.py --since 2026-05-22T12:00:00 --until 2026-05-23T06:00:00
scan_codex_sessions.py --days 3
```

Useful flags:

- `--codex-dir PATH`: default `${CODEX_HOME:-~/.codex}`
- `--limit N`: cap candidate sessions
- `--chars N`: max characters per safe snippet
- `--compact`: one line per session for `distill`
- `--jsonl`: machine-readable output for custom processing

## Summary Rules

- Identify the dominant workstream from evidence, not from thread count alone.
- Group related sessions by repo/cwd, goal, and outcome.
- Separate completed work, interrupted work, investigations, commits/pushes, and unresolved risks.
- Use exact dates and time ranges when the user used relative words like today/yesterday.
- Prefer Traditional Chinese unless the user asks otherwise.
- Do not paste raw transcripts, full prompts, tokens, shell snapshots, or secrets.
- Keep message snippets short and paraphrase unless exact wording is essential.

## Verification

Before finalizing:

- Check the top 3-8 candidate logs directly when the distill summary depends on them.
- Inspect `turn_aborted`, `patch_apply_end`, command calls, and final assistant messages for completion state.
- If a recovered task belongs to another repo and the user asks to continue it, read that repo's `AGENTS.md` and `README.md` before editing.
- Report any gap: missing logs, ambiguous day boundary, failed `distill`, or insufficient evidence.

## Fallback

If `distill` is unavailable or fails, use the helper output directly, but narrow the time range or lower `--limit` before reading raw logs. Do not broaden into unrestricted `rg` across all `~/.codex` logs unless the helper output is insufficient.
