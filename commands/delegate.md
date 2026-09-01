---
description: Delegate a low-complexity task to a free opencode model (auto-fallback)
argument-hint: "[--apply] zen|openkilo|cline|pi <task…>"
---

Parse the arguments below. If the first token is `--apply`, drop it and set
`apply: true` (BUILD mode — the model edits files in the current directory).
The next whitespace-delimited token is the provider **group**; everything after
it is the **task**.

Arguments: $ARGUMENTS

Call the `mcp__opencode-delegate__delegate` tool with:

- `group` — the group token (must be one of `zen`, `openkilo`, `cline`, `pi`)
- `prompt` — the rest of the arguments, phrased as a single self-contained
  instruction
- `apply` — `true` only if `--apply` was given; then also pass `cwd` if the
  edit target is not the current directory

Return the model's answer verbatim, then, on its own line, the
`>>> answered by …` marker from the tool's footer. In `--apply` runs, then show
`git diff` and run the project's build/test/lint before calling it done. If the
tool reports the group is exhausted, say so and either retry with a different
group or handle the task directly and label it `[degraded]`.
