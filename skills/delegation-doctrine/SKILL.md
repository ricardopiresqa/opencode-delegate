---
name: delegation-doctrine
description: >-
  When and how to offload low-complexity Claude Code work to free models via
  the opencode-delegate MCP tool, to conserve Claude tokens. Use when a task
  is bulk classification / triage, short summarisation, field extraction,
  mechanical reformatting or syntax conversion, repetitive boilerplate or
  fixtures, or trivial textual lookups — especially at volume (3+ similar
  items).
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
- applying diffs or any action with a side effect (file writes, commits)
- a task smaller than the hand-off cost — a word you already know

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
