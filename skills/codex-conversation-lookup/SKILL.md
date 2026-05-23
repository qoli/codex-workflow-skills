---
name: codex-conversation-lookup
description: Locate, inspect, and safely summarize local Codex conversation logs by UUID. Use when a user provides a Codex conversation/thread UUID and asks to read, explain, recover, continue, hand off, 查看、接續、恢復、回看、理解 prior Codex Desktop/CLI thread context without exposing raw private transcripts.
---

# Codex Conversation Lookup

## 目的

使用這個 skill，把 Codex conversation UUID 轉成精簡的閱讀路線與接續摘要。把每個 UUID 都視為不可信輸入，只搜尋使用者 Codex home 底下已存在的本機索引與 logs。

不要在回覆中貼出完整 JSONL logs、shell snapshots、prompts、tokens 或原始 transcript。只分享完成使用者請求所需的最小上下文。

## 快速開始

先跑 helper：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/codex-conversation-lookup/scripts/lookup_codex_thread.py" <uuid>
```

把輸出當成地圖，不要直接當成最終答覆。接著只讀取回答使用者問題所需的特定 log 區段。

## 工作流

1. 在 shell command 中使用 UUID 前，先驗證 UUID 形狀。偏好 fixed-string search，避免把 UUID 插進複雜 shell expression。
2. 查 `${CODEX_HOME:-$HOME/.codex}/session_index.jsonl`，取得 thread name 與 update time。
3. 在下列位置找到符合的 `rollout-*.jsonl`：
   - `${CODEX_HOME:-$HOME/.codex}/sessions/`
   - `${CODEX_HOME:-$HOME/.codex}/archived_sessions/`
4. 檢查 `session_meta`，確認 thread id、建立時間、`cwd`、originator、CLI version、source，以及可用時的 model。
5. 從 user 與 assistant messages 建立時間線。第一個 user message 可能是 workspace instructions；後續較短的 user messages 通常才是真正任務。
6. 如果任務是接續，只在需要時檢查 tool events、aborted turns、patch events、command calls、command outputs、shell snapshots。
7. 如果還原出的 `cwd` 指向另一個 workspace，且使用者要接續任務，先讀那個 workspace 的 `AGENTS.md` 與 `README.md`，再進行修改。
8. 回覆時包含：
   - 這段 thread 在做什麼
   - 發生在哪裡 (`cwd`) 與時間
   - 應該從哪裡開始讀
   - 哪些事已完成、中斷或仍有風險
   - 接續任務的具體下一步

## 閱讀優先順序

先讀 `session_meta`，再讀 user messages，接著讀 assistant final/commentary，最後才讀 tool events。使用者後來的修正優先於 assistant 較早的假設。把 `<turn_aborted>` 視為「前一段方向可能已被後續訊息取代」的訊號。

如果要接續任務，明確檢查：

- `turn_aborted`
- 未完成 commands 或 long-running sessions
- `patch_apply_end` 與檔案變更
- `${CODEX_HOME:-$HOME/.codex}/shell_snapshots/` 底下的 shell snapshots
- 如果任務移往還原出的 workspace，檢查該 workspace 的未提交變更

## 安全輸出規則

- 摘要即可，不要傾倒 raw transcripts。
- 不要把 Codex JSONL logs commit 或 copy 進 repo。
- 不要引用 secrets、tokens、private prompts 或大型 tool outputs。
- 討論證據時，command outputs 與 message snippets 要保持短。
- 不需要精確原文時，改用改寫摘要。

## 手動命令

如果目前 workspace 要求 shell commands 加上 RTK 前綴，使用 `rtk proxy`。

```bash
UUID="<uuid>"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"

rtk proxy rg -n --fixed-strings "$UUID" "$CODEX_DIR/session_index.jsonl"
rtk proxy find "$CODEX_DIR/sessions" "$CODEX_DIR/archived_sessions" -name "*${UUID}*.jsonl" -print
rtk proxy find "$CODEX_DIR/shell_snapshots" -name "${UUID}.*.sh" -print
```

Metadata：

```bash
rtk proxy jq -r '
  select(.type=="session_meta")
  | [.payload.id,.payload.timestamp,.payload.cwd,.payload.originator,.payload.cli_version,.payload.source]
  | @tsv
' "$LOG"
```

Message timeline：

```bash
rtk proxy jq -r '
  select(.type=="response_item"
    and .payload.type=="message"
    and (.payload.role=="user" or .payload.role=="assistant"))
  | [
      .timestamp,
      .payload.role,
      ((.payload.content // [])
        | map(.text // .output_text // empty)
        | join(" ")
        | gsub("\n";" ")
        | .[0:260])
    ]
  | @tsv
' "$LOG"
```
