---
name: delegation-doctrine
description: >-
  When and how to offload low-complexity Claude Code work to free models via
  the opencode-delegate MCP tool, to conserve Claude tokens. Use when a task
  is bulk classification / triage, short summarisation, field extraction,
  mechanical reformatting or syntax conversion, repetitive boilerplate or
  fixtures, or trivial textual lookups — especially at volume (3+ similar
  items); when a job splits into several independent activities that each need
  an agent (delegate them in parallel instead of spawning Claude subagents);
  or for a mechanical, well-scoped file edit (BUILD mode, apply=true).
---

# Delegation doctrine

`opencode-delegate` exposes an MCP tool, **`mcp__opencode-delegate__delegate`**,
that runs a prompt on a FREE model from one of four `opencode` provider groups
(`zen`, `openkilo`, `cline`, `pi`) with automatic in-group fallback and
cooldown. The model computation costs **no Claude tokens** — only your
orchestration turn does. So delegation pays off on *volume* and on work you
would otherwise spend real reasoning tokens on.

## Delegate (without being asked) when the subtask is

- classification / labelling / triage (sentiment, intent, category)
- a summary of ≤ 1 paragraph, or field extraction from a blob of text
- mechanical reformatting, syntax / format conversion, normalisation
- repetitive boilerplate, fixtures, test data
- a trivial textual lookup or query rephrasing
- **especially** any of the above at volume (3+ similar items)

## Do NOT delegate

- final architectural decisions, risk assessment, security judgement
- anything needing deep multi-step reasoning you would not trust a small
  model with
- commits, pushes, deploys, or any outward-facing / irreversible action
- a task smaller than the hand-off cost — a word you already know

(Mechanical *file edits* can be delegated in BUILD mode — see below — but the
plan, the review, and anything non-mechanical stay with you.)

## Parallel multi-activity work — delegate, don't fan out Claude subagents

When a job splits into several **independent** activities that each need an
agent — a batch of files to classify, several modules to summarise, a set of
fixtures to generate, per-directory mechanical refactors — issue one
`delegate` call per activity (they run as separate `opencode` subprocesses at
$0) instead of spawning Claude subagents for them. Reserve Claude subagents for
the parts that actually need Claude's reasoning (architecture, security, risk,
ambiguous judgement). Collect the results and integrate them yourself.

## BUILD mode — `apply: true`

`delegate` with `apply: true` (and `cwd`) runs the winning free model with
`--auto`, so it **edits files in `cwd` directly** and returns a summary. Use it
only for a **mechanical, well-scoped** change you could describe precisely:
rename a symbol across a package, add a boilerplate test file, apply a
find-and-replace, scaffold a component from a template. After it returns,
**review the diff** (`git -C <cwd> diff`) and run the project's build/test/lint
— the change is not done until that passes. Keep architecture, security-relevant
code, and anything requiring judgement in your own hands.

## Choosing a group

Any group handles most delegable tasks. Rough guidance:

| Need | Group | Note |
|---|---|---|
| fast generalist — summaries, extraction, rewrite | `openkilo` | largest pool, deepest fallback |
| code boilerplate / mechanical refactor | `zen` (`laguna-s-2.1-free`) or `openkilo` (`poolside/laguna-s-2.1:free`) | code-tuned |
| long document to read / ~1M context | `pi` (`moonshotai/kimi-k3`) | large context |
| quick, reasoning-capable, structured output | `pi` (`openai/gpt-oss-20b`) | fastest |
| batch triage of many short items | `zen` / `openkilo` nemotron `*-lightning` | throughput, higher latency |

Pass `preferred_model` only when the task clearly suits one; otherwise let the
runner start from the top of the group.

## Reading the result

The tool returns the answer followed by a `>>> answered by <group>/<model>`
line plus any fallback / cooldown notes. If it returns an error that the group
is exhausted, try another group, or do the task yourself and label the output
`[degraded]`.

See **`model-catalog.md`** in this skill directory for the full per-model
catalogue (status, latency, recommended use). The `catalog` MCP tool returns
the same content.
