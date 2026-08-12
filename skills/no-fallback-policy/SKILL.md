---
name: no-fallback-policy
description: Use when designing, reviewing, or editing code paths that might add fallback behavior. This project prefers explicit failure over hidden fallback; fallback code is forbidden unless the user explicitly requests it in the current task.
---

# No Fallback Policy

## Rule

This project prefers explicit failure over hidden fallback.

Do not add fallback code unless the user explicitly requests it in the current
task. Prior project habits, compatibility concerns, "best effort" behavior, or
agent judgment are not enough.

If required data is missing, throw an explicit error or fail the operation.

## Use This Skill When

Use this skill before adding, reviewing, or preserving code that:

- keeps going after a missing file, missing field, failed parse, failed command,
  failed request, or invalid invariant
- substitutes any value, source, implementation, algorithm, artifact, or state
  after the expected path fails
- uses `try/catch`, `except`, `recover`, `|| default`, `?? default`, or similar
  control flow around required semantic state
- mentions fallback, compatibility, migration, placeholder, mock, default,
  best effort, provenance, cache recovery, or inferred source identity

## Forbidden By Default

Do not introduce these behaviors unless the user explicitly asks for fallback in
the current task:

- legacy compatibility path
- silent default value
- placeholder data
- mock data in production path
- best-effort migration
- auto-created missing state
- catch-and-continue behavior
- fallback algorithm
- inferred provenance when source is unknown

## Required Behavior

When required state is absent, malformed, inconsistent, or unverifiable:

1. Fail the operation explicitly.
2. Preserve the original error cause.
3. Report the missing or invalid requirement.
4. Do not produce valid-looking output from substitute data.
5. Do not claim success from a degraded or guessed path.

Prefer errors that name the failed invariant:

```text
missing canonical artifact: path/to/file.json
invalid provenance: source_id is required
malformed state: config.version must be 2
```

## If Fallback Seems Necessary

Stop before implementing fallback. Report these four facts to the user:

1. exact failure being protected against
2. why explicit failure is not acceptable
3. exact code path affected
4. how tests will prove the fallback was not silently used

Only implement fallback after the user explicitly approves it for the current
task.

## Review Checklist

Before finishing a change, check:

- [ ] no new legacy compatibility path was added
- [ ] no required value is silently defaulted
- [ ] no production path uses placeholder or mock data
- [ ] no missing state is auto-created to make execution continue
- [ ] no malformed state is repaired without user approval
- [ ] no catch block continues after an invariant failure
- [ ] no algorithm switches silently after primary logic fails
- [ ] no provenance is inferred when the source is unknown
- [ ] tests assert explicit failure for missing or invalid required data

## Acceptable Non-Fallback Patterns

These are not fallback when they are part of the primary contract:

- validation followed by explicit error
- retry requested by the user or already specified by the feature contract
- optional feature disabled with a visible "not available" result
- UI-only empty state that does not stand in for semantic data
- test fixtures that are isolated from production paths

If there is doubt, treat it as fallback and stop for user approval.

## Completion Report

When this skill affects the work, include a short note:

- whether fallback was added: yes/no
- which missing/invalid states now fail explicitly
- which tests prove the failure behavior
