# Blog Material

These skills are useful as public writing material because they came from real
workflow failures, not abstract prompt engineering.

## Context Recovery

Skills:

- `codex-conversation-lookup`
- `codex-session-distill-search`

Story angle: an agent does better follow-up work when it can recover the right
local thread, cwd, date, completion state, and interrupted turns. The important
shift is from "remembering a chat" to building a safe route map for continuation.

Shareable scenes:

- Continue a task from a Codex UUID across a different repo.
- Summarize what happened yesterday without exposing raw private transcripts.
- Distinguish dominant workstreams from noisy session titles.

## Debugging Discipline

Skill:

- `observability-first-debugging`

Story angle: debugging should start by bounding uncertainty. The skill is useful
because it slows the agent down at the exact moment it wants to make a speculative
fix.

Shareable scenes:

- Add targeted logs at a state transition before changing code.
- Use existing logs, database state, or runtime health checks before proposing a fix.
- Remove temporary instrumentation after the root cause is bounded.

## Second-Model Consultation

Skill:

- `cli-model-chat`

Story angle: a second model is most useful as a narrow one-to-one reviewer, not
as a hidden multi-agent system. The wrapper keeps credentials local, asks one
focused question, and can isolate the Codex backend when explicitly requested.

Shareable scenes:

- Ask a second model to review a design decision.
- Paste a focused patch or error instead of giving broad filesystem access.
- Keep model selection and secret handling explicit.

## Xiaohongshu Production Workflow

Skills:

- `xhs-figma-cards`
- `xhs-publish-handoff`

Figma automation:

- Tested with [qoli/figma-mcp-go](https://github.com/qoli/figma-mcp-go).
- Other Figma MCP or automation adapters can work if they provide equivalent
  page inspection, frame creation/update, text editing, and asset import.

Story angle: Xiaohongshu publishing works better when design, asset validation,
browser filling, and final publishing authority are separated. A working Figma
automation adapter is required for canvas work; without one the skill can only
draft or validate, not actually update Figma.

Shareable scenes:

- Convert a blog post into a multi-card Figma package.
- Route style-heavy covers through image generation, then place the selected
  bitmap back in Figma.
- Validate exported PNG order, dimensions, title/body length, and hashtags before
  opening the creator page.
- Fill the composer through a real browser session but stop before final publish.
