---
name: publish-skill-to-repository
description: Use when asked to copy an installed Codex Skill into this repository and publish it. Always delegate the copy and README update to a gpt-5.6-luna subagent with reasoning_effort=medium, then verify the exact contents, validate the Skill, commit only scoped files, push the current branch, and confirm remote SHA parity.
---

# Publish Skill to Repository

Publish an existing installed Codex Skill from its canonical local folder into
this repository. Treat the requested Skill as the artifact being copied; do not
apply its instructions merely because it is the publication target.

## Required Delegation

Before changing repository files, spawn one subagent with:

- model: `gpt-5.6-luna`
- reasoning effort: `medium`
- forked context: `none`

Give the subagent the explicit source path, repository path, destination path,
README conventions, and current worktree status. Have it perform the source
inspection, copy, README update, and initial validation. Do not let it commit or
push. Record the exact model, reasoning effort, and fork setting used in the
delegation call. If the call rejects any requested setting, stop.

If Luna Medium or subagents are unavailable, stop and report that requirement.
Do not substitute another model or silently complete the work in the main agent.

## Workflow

### 1. Establish the exact scope

Resolve all of these before mutation:

- canonical source Skill directory
- Skill name from the source `SKILL.md` frontmatter
- destination `skills/<skill-name>/`
- repository root, current branch, upstream, and remote
- complete worktree and staged state
- pre-mutation tracked diff and untracked-file inventory

Require the source directory and `SKILL.md` to exist. Require the frontmatter
name to match `[a-z0-9-]+`, and require the canonical destination to remain
inside the repository's `skills/` directory. Inspect the full source inventory
for local secrets or state such as `.env`, caches, credentials, or session data.
Reject symlinks that resolve outside the source Skill directory. If any unsafe
item is present, stop and ask what may be published; never omit or publish it
silently.

Preserve unrelated modified, staged, and untracked files. Stop if `README.md`
already has tracked or staged changes because path-level staging cannot isolate
ownership safely. If the destination already exists and differs from the source,
stop and report the exact differences. Require a separate explicit update scope
before overwriting or deleting any existing destination file.

### 2. Delegate the repository edits

Have the Luna Medium subagent:

1. Copy the complete publishable source Skill directory to
   `skills/<skill-name>/`, preserving file contents and relative paths.
2. Update the root `README.md` using its existing structure:
   - add exactly one row under the existing `## Skills` table
   - add exactly one command inside the existing `## Install` code block
   - add exactly one command inside the existing `## Validate` code block
   - preserve all surrounding order, wording, and formatting
3. Avoid edits outside the destination Skill directory and the exact README
   entries.
4. Run the initial Skill validator and report every changed path.

If the README does not have the expected sections, stop instead of inventing a
new documentation layout.

### 3. Verify independently

After the subagent finishes, the main agent must verify:

- source and destination publishable file inventories match
- every copied file is byte-identical to its source
- YAML frontmatter name matches the destination directory
- `quick_validate.py skills/<skill-name>` succeeds
- `git diff --check` succeeds for the scoped files
- the README diff contains only the intended table, install, and validation
  entries
- no unrelated file is included in the intended commit
- every allowlist-external tracked diff and untracked path matches the
  pre-mutation snapshot

Do not claim success from the subagent report alone.

### 4. Commit only the approved paths

Require an existing tracking upstream. Fetch it, record its SHA as
`remote_before`, and require it to be an ancestor of local `HEAD`. Do not
automatically merge, rebase, change branches, modify remotes, or force-push.

Use an explicit path allowlist containing only:

- `README.md`
- `skills/<skill-name>/`

Never use `git add -A` in a mixed worktree. Review the scoped staged diff. If
unrelated changes are already staged, commit the allowlisted paths explicitly so
the user's staged state remains staged and outside the commit.

After committing, inspect the new commit with `git diff-tree` and require every
changed path to match the allowlist. Preserve any unrelated staged state.

### 5. Publish and prove it

Commit with a terse message naming the published Skill. Fetch once more before
pushing and require the upstream SHA to still equal `remote_before`. Then push
the current branch to its confirmed upstream without `--force` or
`--force-with-lease`. Publication is authorized only when the user asked to
publish or push.

After pushing, fetch the remote branch and require:

```text
local HEAD SHA == remote branch SHA
```

Report the destination, validation result, commit SHA, remote branch, SHA parity,
and any unrelated worktree changes deliberately left untouched.

## Stop Conditions

Stop without publishing when any of these is true:

- Luna Medium delegation cannot be performed
- source path or source `SKILL.md` is missing
- source contains unreviewed secrets or local state
- source name or symlink layout can escape the allowed directories
- `README.md` contains pre-existing tracked or staged changes
- destination already exists and differs from the source
- README structure is incompatible with the required bounded edit
- source and destination differ after copying
- validation or `git diff --check` fails
- commit scope contains an unrelated path
- tracking upstream is missing
- remote branch advanced or the push and commit tree cannot be verified

Do not replace a failed required step with a best-effort alternative.

## Completion Checklist

- [ ] Luna Medium subagent performed the copy and README work
- [ ] delegation call used `gpt-5.6-luna`, `medium`, and `fork_turns=none`
- [ ] main agent independently verified content identity and validation
- [ ] README table, install, and validation entries are present
- [ ] commit contains only the approved paths
- [ ] push succeeded without force
- [ ] local and remote SHAs match
- [ ] unrelated worktree state remains untouched
