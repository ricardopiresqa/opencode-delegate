# Changelog

## 0.3.0 — 2026-10-21

Re-probed catalogue + stop paying for failures we already know about.

Measured on 4 days of real use before this release: 129 of 586 attempts
succeeded (22 %). Most of the waste was one provider being down (expired
login, local gateway off) and the runner paying one failed attempt per model,
on every call, plus models that never once answered.

- **Catalogue re-probed (2026-10-21)** over every model `opencode models`
  lists for the supported providers (answer `OK` and 17×23−45 correctly):
  zen 9/10, openkilo 13/14, pi 3/9 (four retired upstream), clixad 4/4,
  cline 0/6 that day (expired login). `GROUPS` reordered fastest-first;
  retired/broken models moved to `KNOWN_DEAD`; `model-catalog.md`
  regenerated from the probe.
- **New optional group `clixad`** — Clixad models through a local
  OpenAI-compatible gateway registered in `opencode` as provider `thoth`.
  The gateway is checked (2 s) before its models; when it is down the group
  is skipped in one step. URL: `OPENCODE_DELEGATE_GATEWAY_URL`.
- **Aliases**: `kilo` → `openkilo`, `opencode` → `zen`.
- **Persisted pauses** (in `cooldown.json`): an auth failure (401 / 403 /
  unauthorized) pauses the whole provider for 30 min; 3 failures in a row
  pause the group for 15 min. A `preferred_model` you name explicitly still
  runs through them.
- **Auto-quarantine**: a model whose last 10 attempts (7-day window) all
  failed is skipped until one success.
- **Attempts log** `~/.opencode-delegate/attempts.jsonl`: model, ok, kind,
  seconds, and for failures a safe error code (HTTP status + labels from a
  closed list — never the provider's free text, which can quote the prompt).
- `.gitignore`: local state, probe outputs, caches and `.env*`.
- Tests: aliases, safe error code, auto-quarantine, provider pause on auth,
  gateway-down skip (offline; state isolated in a temp dir).

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
