# opencode-delegate

**Offload low-complexity Claude Code work to *free* models — save tokens.**

A Claude Code plugin that adds one MCP tool, `delegate`, which runs a prompt on
a free model from an [`opencode`](https://opencode.ai) provider group
(**OpenCode Zen**, **OpenKilo**, **Cline**, **Pi**), with automatic in-group
fallback and cooldown. The model computation runs as a local `opencode`
subprocess and costs **no Claude tokens** — only the short orchestration turn
that calls the tool does.

Use it for the work that does not need Claude's full ability: bulk
classification/triage, short summaries, field extraction, mechanical
reformatting, boilerplate, fixtures, trivial lookups — especially at volume.

---

## Honest scope

- **Savings are on the delegated computation only.** Your orchestrator turn
  still runs on Claude. This pays off on *volume* and on work you would
  otherwise burn real reasoning tokens on — not on one-off trivia.
- **It ships no accounts.** Each `opencode` provider is a separate plugin with
  its own setup and auth. You bring those.
- **Free tiers rate-limit and change.** Fallback + cooldown smooth over it;
  they do not make a dead provider work.
- **Each `opencode run` carries a large fixed steering prompt** (`$0` on these
  free models, but a few seconds of latency). Not worth it for a one-word
  answer you already know.
- Check each provider's terms for programmatic / orchestrated use.

---

## How it works

```
Claude Code (orchestrator)
      │  calls MCP tool  mcp__opencode-delegate__delegate(group, prompt)
      ▼
mcp/server.py  ──►  mcp/core.py
                      │  try group models best-first
                      │  skip cooling models
                      │  on transient fail → 5-min cooldown, next model
                      │  on fatal fail     → 24-h cooldown, next model
                      ▼
              opencode run -m <model> --format json "<prompt>"   (local, $0)
                      ▼
        answer  +  ">>> answered by <group>/<model> (attempt N)"
```

`core.py` is a faithful port of a standalone `delegate-run.py`. There is no
shell involved — the prompt is passed to `opencode` as a single argv, so there
is nothing to escape and no injection surface.

### Provider groups

| group | prefix | provider |
|---|---|---|
| `zen` | `opencode/` | OpenCode Zen native models |
| `openkilo` | `openkilo/` | OpenKilo plugin |
| `cline` | `cline/` | Cline recommended free models |
| `pi` | `pi-free/` | Pi free models (NVIDIA NIM) |

Curated live lists and per-model guidance: [`skills/delegation-doctrine/model-catalog.md`](skills/delegation-doctrine/model-catalog.md).
Probed 2026-08-30: **30 / 41** free models live.

---

## Requirements

- **Claude Code** (for the plugin) — or any MCP client (see *Manual install*).
- **Python 3.8+** on `PATH` as `python3` (Windows: see note below).
- **[`opencode`](https://opencode.ai) CLI** installed and on `PATH`.
- At least one provider group configured (below). You do **not** need all four.

---

## Install (Claude Code plugin)

```
/plugin marketplace add ricardopiresqa/opencode-delegate
/plugin install opencode-delegate@opencode-delegate
```

Restart Claude Code. Verify:

```
/mcp                     # opencode-delegate should be listed / connected
/delegate pi reply only: ok
```

**Windows note:** the plugin runs `python3 mcp/server.py`. If `python3` is not
on your `PATH` (only `python` is), use the *Manual install* below with
`"command": "python"`, or create a `python3` shim.

---

## Provider setup (bring your own)

`opencode-delegate` calls these models; it does not provision them. Configure
whichever groups you want in your `opencode` config
([`config/opencode.example.jsonc`](config/opencode.example.jsonc) is a
skeleton):

| group | setup |
|---|---|
| `zen` | `opencode auth login` → **OpenCode** |
| `openkilo` | add the `openkilo` plugin to your `opencode` config; follow its README |
| `cline` | add the `cline-free` plugin, then `cline auth` |
| `pi` | add the `pi-free-provider` plugin; follow its README |

Confirm what actually answers for you:

```
opencode models
opencode run -m opencode/big-pickle --format json "reply only: ok"
```

---

## Usage

### Automatic (the doctrine skill)

The bundled **`delegation-doctrine`** skill tells Claude *when* to reach for the
tool without being asked: bulk classification/triage, ≤1-paragraph summaries,
field extraction, mechanical reformatting/syntax conversion, repetitive
boilerplate/fixtures, trivial lookups — especially 3+ similar items. It is a
guideline Claude follows by judgement, not enforced routing; on a borderline or
tiny task Claude may still do it inline.

### Explicit — slash command

```
/delegate openkilo classify the sentiment of each line as pos/neg/neutral:
<paste lines>
```

First token = group; the rest = the task.

### Explicit — MCP tool

Ask Claude to "use the `delegate` tool", or in an SDK/other MCP client call:

```jsonc
{
  "name": "delegate",
  "arguments": {
    "group": "pi",
    "prompt": "Extract {name, date, total} as JSON from:\n<text>",
    "preferred_model": "openai/gpt-oss-20b",   // optional
    "timeout_s": 100                            // optional, 20–280
  }
}
```

Returns the answer, then `>>> answered by <group>/<model> (attempt N)` and any
fallback/cooldown notes. On a fully exhausted group it returns an error listing
what was tried.

### Other tools

- **`list_models`** `{ "group"?: "openkilo" }` — curated live list + fallback
  order, plus known-dead entries.
- **`catalog`** — the full catalogue markdown (status, latency, recommended use).

### Optional isolation subagent

`agents/delegate-runner.md` (runs on Haiku) wraps the tool for the rare case
where a delegated result is large and you want it condensed before it hits the
main context. For normal use, call the tool directly.

---

## Fallback & cooldown

- tries models best-first (your `preferred_model` first, if given);
- skips any model currently in cooldown;
- **transient** failure (rate limit / temporary / timeout / network) → 5-min
  cooldown, try next;
- **fatal** failure (retired / not supported / needs sign-in / 404 / 410) →
  24-h cooldown, try next;
- errors only when every model in the group is down or cooling.

State: `~/.opencode-delegate/cooldown.json` — override the directory with
`OPENCODE_DELEGATE_HOME`. Override the `opencode` binary with
`OPENCODE_DELEGATE_BIN`.

---

## Manual install (no plugin / other MCP client)

Copy [`config/mcp.json.example`](config/mcp.json.example) to your project as
`.mcp.json` (or merge the `mcpServers` block into `~/.claude.json`), and set the
absolute path to `mcp/server.py`. Use `"command": "python"` if that is your
interpreter name.

The server is standard-library only — nothing to `pip install`.

---

## Development

```
python3 tests/test_core.py      # offline: classification, prefixes, parsing
```

`mcp/core.py` holds all the logic and has no MCP dependency, so it is the place
to add models (edit `GROUPS` — order is fallback priority), tune the
transient/fatal regexes, or change cooldown durations. `mcp/server.py` is only
JSON-RPC glue.

The curated model lists reflect a probe on 2026-08-30. Re-probe with
`opencode models --refresh` and a minimal `opencode run` per model before
relying on them.

Contributions welcome — especially fresh probe results and new free providers.

## License

MIT — see [LICENSE](LICENSE).
