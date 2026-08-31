# Changelog

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
