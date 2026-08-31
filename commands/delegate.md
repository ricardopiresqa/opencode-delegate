---
description: Delegate a low-complexity task to a free opencode model (auto-fallback)
argument-hint: "zen|openkilo|cline|pi <task…>"
---

The first whitespace-delimited token of the arguments below is the provider
**group**; everything after it is the **task**.

Arguments: $ARGUMENTS

Call the `mcp__opencode-delegate__delegate` tool with:

- `group` — that first token (must be one of `zen`, `openkilo`, `cline`, `pi`)
- `prompt` — the rest of the arguments, phrased as a single self-contained
  instruction

Return the model's answer verbatim, then, on its own line, the
`>>> answered by …` marker from the tool's footer. Do not add analysis unless
asked. If the tool reports the group is exhausted, say so and either retry
with a different group or handle the task directly and label it `[degraded]`.
