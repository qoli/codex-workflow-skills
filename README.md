# Codex Workflow Skills

Practical Codex skills extracted from real local workflows. These skills focus on
recovering context, improving debugging discipline, consulting a second model,
and running Xiaohongshu content workflows through Figma plus browser handoff.

## Skills

| Skill | Scenario |
| --- | --- |
| `codex-conversation-lookup` | Recover and summarize a specific local Codex thread by UUID without dumping raw transcripts. |
| `codex-session-distill-search` | Summarize recent Codex work across many sessions and turn logs into a safe activity recap. |
| `observability-first-debugging` | Debug unclear failures by adding targeted evidence before changing behavior. |
| `cli-model-chat` | Ask a focused second-model question through a local one-to-one chat wrapper. |
| `xhs-figma-cards` | Turn blog posts, product notes, or launch notes into Xiaohongshu card designs in Figma. |
| `xhs-publish-handoff` | Validate an approved Xiaohongshu image-post package and optionally fill the creator page, stopping before final publish. |

## Requirements

- Codex or another agent runtime that can load `SKILL.md` directories.
- Python 3 for helper scripts.
- `git`, `rg`, and ordinary Unix shell tools.
- For `cli-model-chat`: an OpenAI-compatible API key such as `DEEPSEEK_API_KEY`, or explicit use of the Codex provider.
- For `codex-session-distill-search`: local Codex session logs and, optionally, a local OpenAI-compatible distill endpoint.
- For Xiaohongshu/Figma work: a Figma automation path that can inspect pages,
  create or update frames, edit text layers, and import assets. This workflow
  was tested with [qoli/figma-mcp-go](https://github.com/qoli/figma-mcp-go),
  but other Figma MCP or automation adapters can work if they expose equivalent
  read/write capabilities. Without a working Figma adapter, the agent can draft
  copy or validate exported images, but it cannot claim canvas updates.
- For Xiaohongshu browser filling: an existing CDP-enabled browser session, commonly Arc or Chrome at `http://localhost:9222`.

## Install

Copy or symlink the skill directories you want into your agent's global skills
directory. For Codex, that is usually:

```sh
mkdir -p "$HOME/.codex/skills"
ln -s "$PWD/skills/codex-conversation-lookup" "$HOME/.codex/skills/codex-conversation-lookup"
ln -s "$PWD/skills/codex-session-distill-search" "$HOME/.codex/skills/codex-session-distill-search"
ln -s "$PWD/skills/observability-first-debugging" "$HOME/.codex/skills/observability-first-debugging"
ln -s "$PWD/skills/cli-model-chat" "$HOME/.codex/skills/cli-model-chat"
ln -s "$PWD/skills/xhs-figma-cards" "$HOME/.codex/skills/xhs-figma-cards"
ln -s "$PWD/skills/xhs-publish-handoff" "$HOME/.codex/skills/xhs-publish-handoff"
```

If a skill already exists at the destination, inspect it before replacing it.

## Validate

If your Codex installation includes the skill creator validator:

```sh
python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" skills/codex-conversation-lookup
python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" skills/codex-session-distill-search
python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" skills/observability-first-debugging
python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" skills/cli-model-chat
python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" skills/xhs-figma-cards
python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" skills/xhs-publish-handoff
```

## Blog Angles

See [docs/blog-material.md](docs/blog-material.md) for writing angles and concrete
scenarios these skills came from.

## Privacy Notes

The context-recovery skills are designed to summarize local Codex logs safely.
They should not publish raw transcripts, shell snapshots, secrets, private
prompts, or large tool outputs.
