---
name: observability-first-debugging
description: Use when debugging bugs, incidents, flaky tests, regressions, production issues, or unclear system behavior where the root cause is not yet bounded. Applies when Codex should increase observability first by adding targeted logs, metrics, traces, or assertions before proposing a fix. Triggers include requests to debug, investigate, instrument, add logs, narrow down, reproduce, or "wrap the problem with logs".
---

# Observability-First Debugging

## Overview

Do not jump from symptoms to fixes when the failure surface is still wide.

**Core principle:** expand observability until the problem is bounded, then fix the bounded problem.

## When to Use

Use this skill when:

- the bug reproduces but the cause is unclear
- multiple layers could be responsible
- a test fails without enough local evidence
- the problem appears flaky, timing-sensitive, or environment-dependent
- a user asks to add logs, instrument code, or investigate before fixing

Do not lead with broad instrumentation when the root cause is already obvious from current evidence.

## Rule

Before making speculative code changes, add enough targeted observability to answer the next unknown.

Instrumentation should reduce uncertainty, not just increase log volume.

## Workflow

1. Define the symptom precisely.
2. State the current unknowns.
3. Choose the narrowest boundary that can separate likely causes.
4. Add targeted instrumentation at that boundary.
5. Reproduce and inspect the new evidence.
6. Repeat only until the failure surface is bounded.
7. Apply the fix to the bounded cause.
8. Remove temporary instrumentation and keep only durable observability that has ongoing value.

## Where to Instrument

Prefer adding evidence at decision points and boundaries such as:

- request entry and exit
- state transitions
- condition branches with surprising outcomes
- external API or database calls
- retry loops, timeout paths, and exception handlers
- async queue handoffs, worker boundaries, and concurrency joins
- data parsing, normalization, and schema validation points

## What Good Instrumentation Looks Like

Good instrumentation is:

- targeted to a concrete hypothesis or unknown
- cheap enough to run during reproduction
- reversible if it is only for local diagnosis
- structured enough to correlate inputs, state, and outputs
- specific about IDs, branches, counts, timing, and error context

Include identifiers that let you stitch a single failing path together across layers.

## What to Avoid

- adding logs everywhere without a question they answer
- changing behavior while instrumenting unless necessary for safety
- logging secrets, tokens, passwords, or sensitive payloads
- leaving noisy temporary logs in hot paths after the issue is understood
- declaring a fix before the new evidence isolates the cause

## Escalation Pattern

Use the smallest step that can answer the next question:

1. existing logs and repro output
2. additional local logs or assertions
3. structured metrics, counters, or timing
4. trace-style correlation across components
5. invasive instrumentation only if lighter steps do not bound the issue

## Output Expectations

When using this skill, report:

- the symptom being investigated
- the unknown being narrowed next
- the instrumentation added
- what the new evidence showed
- whether the issue is now bounded
- which instrumentation was kept or removed
