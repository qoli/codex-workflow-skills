---
name: cli-model-chat
description: Use when Codex needs to ask DeepSeek v4 Pro a focused one-to-one question through a local Python wrapper instead of MCP. Default to DeepSeek for second-model consultation unless the user explicitly names Codex, codex exec, or the Codex provider; only then use the isolated Codex CLI backend.
---

# CLI Model Chat

## Overview

Use `scripts/cli_model_chat.py` to send a prompt to a single external model and print only the assistant response. The default provider is DeepSeek's OpenAI-compatible API with model `deepseek-v4-pro`, thinking mode enabled, `reasoning_effort=high`, `max_tokens=384000`, non-thinking `temperature=1.3`, and local env loading from `skills/cli-model-chat/.env`.

## Required Rules

- Never hardcode API keys in repo files, skill files, shell history, or documentation.
- Pass DeepSeek credentials through `DEEPSEEK_API_KEY`, preferably in the local ignored env file `skills/cli-model-chat/.env`.
- Keep this as a one-to-one chat bridge. Do not add MCP orchestration, multi-agent workflows, consensus, or background subagents unless the user asks.
- If the user does not explicitly mention Codex, `codex exec`, or the Codex provider, use DeepSeek. Omit `--provider` or pass `--provider deepseek`.
- Use `--provider codex` only when the user explicitly asks for Codex as the second model/backend.
- Treat `--provider codex` as a single-turn isolated conversation, not as a repo agent. It must run in a temporary empty directory with `--ephemeral`, `--skip-git-repo-check`, `--ignore-rules`, `--ignore-user-config`, and `--sandbox read-only`.
- The Codex provider must also inject a safety instruction telling the child Codex not to inspect the filesystem, run commands, edit files, open network resources, or use tools.
- Do not pass the current repo path, project files, secrets, or broad filesystem context to the Codex provider. If file context is needed, paste the exact excerpt into the prompt.
- Do not use `--codex-allow-user-config` unless the user explicitly accepts loading their Codex config/profiles for this one run.
- Prefer `--list-models` before changing the default model.
- Use exact V4 model ids: `deepseek-v4-pro` for hard reasoning/coding review, `deepseek-v4-flash` only when speed/cost matter more.
- Do not use legacy aliases `deepseek-chat` or `deepseek-reasoner`; DeepSeek says they currently route to V4-Flash modes and are scheduled for retirement.
- Do not expose or tune a `--max-tokens` CLI option. Always pass DeepSeek V4's maximum available output budget, currently `max_tokens=384000`, so reasoning and final output are not clipped by this wrapper.
- Use `--json` only when the caller needs structured metadata; otherwise stdout should be the model's text answer.

## DeepSeek V4 Usage Guidance

Use `deepseek-v4-pro` when the second model is expected to find mistakes, reason through code, review architecture, compare alternatives, or answer from large pasted context. Official DeepSeek docs describe V4-Pro as a 1.6T total / 49B active MoE model with stronger agentic coding, world knowledge, and Math/STEM/Coding reasoning than current open models; both V4-Pro and V4-Flash support 1M context and the OpenAI ChatCompletions API.

Use `deepseek-v4-flash` for quick sanity checks, simple summarization, and low-cost drafts. DeepSeek describes Flash as faster and more economical, with reasoning close to Pro and simple agent-task performance on par with Pro, but this skill defaults to Pro because its purpose is high-signal second-model consultation.

For DeepSeek V4:

- Keep thinking mode enabled for review, debugging, technical planning, and non-trivial reasoning.
- Use `--reasoning-effort max` only for difficult code review, ambiguous debugging, or prompts where paying extra latency/tokens is justified.
- Use `--thinking disabled` for deterministic extraction, short rewrites, or when temperature should actually affect sampling.
- Do not tune `--temperature` while thinking is enabled; DeepSeek documents that temperature/top_p/presence/frequency penalties have no effect in thinking mode.
- In non-thinking mode, default to `temperature=1.3` for ordinary one-to-one conversation because DeepSeek's temperature guide recommends 1.3 for general conversation.
- Override non-thinking temperature by task: `0.0` for coding/math, `1.0` for data cleaning/analysis, `1.3` for general conversation/translation, and `1.5` for creative writing/poetry.
- Leave output budget to the wrapper. It always sends the maximum V4 output allowance instead of a caller-controlled cap.
- Ask one focused question per call. Provide the relevant files, error, constraints, and desired output shape directly in the prompt.
- For long sessions, prefer explicit `--session` names and periodically restart with `--new-session` when old context is no longer useful.
- Check `--json` usage data on expensive prompts; DeepSeek bills by actual input/output tokens, not by the requested maximum output cap.

## Quick Start

Ask DeepSeek, the default provider. Prefer omitting `--provider` when DeepSeek is intended:

```bash
python3 skills/cli-model-chat/scripts/cli_model_chat.py "Reply with OK only."
```

Ask an isolated single-turn Codex CLI process:

```bash
python3 skills/cli-model-chat/scripts/cli_model_chat.py --provider codex "Reply with OK only."
```

Use a Codex model without loading user config:

```bash
python3 skills/cli-model-chat/scripts/cli_model_chat.py \
  --provider codex \
  --model gpt-5 \
  "Give a second opinion on this design decision: ..."
```

List available DeepSeek models:

```bash
python3 skills/cli-model-chat/scripts/cli_model_chat.py --list-models
```

Ask the default DeepSeek `deepseek-v4-pro` model:

```bash
python3 skills/cli-model-chat/scripts/cli_model_chat.py "Reply with OK only."
```

Ask V4-Pro with maximum thinking effort:

```bash
python3 skills/cli-model-chat/scripts/cli_model_chat.py \
  --reasoning-effort max \
  "Review this patch for correctness risks: ..."
```

Use non-thinking mode for simple short-form output where sampling controls matter:

```bash
python3 skills/cli-model-chat/scripts/cli_model_chat.py \
  --thinking disabled \
  --temperature 0 \
  "Rewrite this sentence in plain English: ..."
```

Use a system prompt:

```bash
python3 skills/cli-model-chat/scripts/cli_model_chat.py \
  --system "You are a concise reviewer." \
  "Review this decision in three bullets: ..."
```

Keep a lightweight local conversation:

```bash
python3 skills/cli-model-chat/scripts/cli_model_chat.py \
  --session deepseek-review \
  "Remember: we are evaluating a local CLI wrapper."
```

Session files are stored under `~/.local/state/cli-model-chat/deepseek/` and should not be committed.

## Provider Selection

Default:

```text
deepseek
```

Use DeepSeek when the task needs a strong non-Codex second opinion with long context, thinking mode, and explicit model/token accounting.

Use Codex only when the user explicitly asks for Codex, `codex exec`, or the Codex provider. The wrapper invokes `codex exec`, writes the final answer through `--output-last-message`, and runs from a temporary empty directory. By default it ignores Codex user config so MCP servers, repo rules, and profiles are not loaded.

Codex CLI does not currently expose a wrapper-level switch that proves "no filesystem tools exist" inside the child agent. This skill therefore uses layered containment: empty temporary cwd, read-only sandbox, ignored rules, ignored user config, ephemeral session, and an explicit prompt instruction forbidding filesystem, shell, network, edit, or tool use. Treat this as a plain-chat wrapper, not an execution agent.

Codex profile usage is intentionally gated:

```bash
python3 skills/cli-model-chat/scripts/cli_model_chat.py \
  --provider codex \
  --codex-allow-user-config \
  --codex-profile my-profile \
  "..."
```

Only use this if the user explicitly wants profile behavior and accepts the weaker isolation boundary.

## DeepSeek Model Selection

Default:

```text
deepseek-v4-pro
```

Override per run:

```bash
python3 skills/cli-model-chat/scripts/cli_model_chat.py --model deepseek-v4-flash "..."
```

Override by environment:

```bash
DEEPSEEK_MODEL=deepseek-v4-pro python3 skills/cli-model-chat/scripts/cli_model_chat.py "..."
```

## Failure Handling

- If `DEEPSEEK_API_KEY` is missing, stop and ask the user to provide it through the environment or a local secret mechanism.
- If model selection fails, run `--list-models` and use an exact returned model id.
- If the API returns a non-2xx response, report the status and response body without printing credentials.

## Source Notes

- DeepSeek V4 API release: `https://api-docs.deepseek.com/news/news260424`
- DeepSeek model ids, context, features, and pricing: `https://api-docs.deepseek.com/quick_start/pricing`
- DeepSeek thinking mode semantics: `https://api-docs.deepseek.com/guides/thinking_mode`
- DeepSeek chat completion parameters: `https://api-docs.deepseek.com/api/create-chat-completion`
