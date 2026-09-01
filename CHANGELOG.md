# Changelog

## 0.2.0 — 2026-09-01

BUILD mode + parallel-delegation doctrine.

- `delegate` gains `apply` (bool) and `cwd` (string). With `apply: true` the
  winning free model runs with `opencode run --auto` in `cwd` and **edits files
  directly**; the tool result flags that the tree changed and to review the diff.
  Timeout defaults to 240 s in this mode; `timeout_s` ceiling raised to 600.
- `mcp/core.py` — new `build_cmd()` helper; `run_one()` / `delegate()` take
  `apply` + `cwd`; apply-mode success no longer requires non-empty summary text.
- `skills/delegation-doctrine/SKILL.md` — new sections: *Parallel multi-activity
  work* (issue one `delegate` call per independent activity instead of spawning
  Claude subagents) and *BUILD mode*. "Do NOT delegate" reworded — mechanical
  file edits are now delegable; commits/pushes/deploys never are.
- `agents/delegate-runner.md` — gains `Read`/`Edit`/`Write`/`Bash`; documents a
  BUILD mode that runs `apply: true`, verifies the diff + build/test/lint, and
  finishes a half-done edit if needed. `maxTurns` 4 → 12.
- `commands/delegate.md` — optional leading `--apply` flag.
- No change to `list_models` / `catalog`, the fallback/cooldown logic, or the
  model catalogue.

## 0.1.0 — 2026-08-31

Initial release.

- `mcp/core.py` — group model lists, automatic in-group fallback, transient
  (5 min) / fatal (24 h) cooldown, `opencode` binary resolution, `opencode run`
  event-stream parsing. Ported from the standalone `delegate-run.py`.
- `mcp/server.py` — dependency-free MCP stdio server exposing `delegate`,
  `list_models`, `catalog`.
- Claude Code plugin: `plugin.json` (registers the MCP server), `commands/delegate.md`,
  `agents/delegate-runner.md`, `skills/delegation-doctrine/`.
- `config/opencode.example.jsonc`, `config/mcp.json.example`.
- `examples/persona-prompts.md` — 9 optional review/build role templates.
- `tests/test_core.py` — offline checks (classification, prefix handling,
  event parsing).

Model catalogue probed 2026-08-30: 30 / 41 free models live across the four
groups.
