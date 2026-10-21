# Free-model catalogue

Models reachable through the `opencode` CLI, grouped by provider plugin. Use
this to decide **whether** and **where** to delegate a low-complexity task.

Probed **2026-10-21** over every model `opencode models` listed for these
providers, one call each: the model had to answer `OK` on line 1 and
`17 × 23 − 45` (= 346) on line 2. Latency includes starting `opencode`
(a few seconds). Free tiers change: re-probe when a model starts failing — the
auto-quarantine (below) already stops paying for one that keeps failing.

The fallback **order** is defined in `mcp/core.py` (`GROUPS`, fastest first);
this document is the human-readable rationale.

## Fallback, cooldown and pauses

- tries the group's models best-first (your `preferred_model` first, if given);
- transient failure → 5-minute cooldown on that model; fatal (retired / 404 /
  410 / not supported) → 24 hours;
- auth failure (401 / 403 / unauthorized) → the whole **provider** is paused
  for 30 minutes; 3 failures in a row → the **group** is paused for 15 minutes;
- a model whose last 10 attempts (7 days) all failed is **auto-quarantined**
  until one success;
- state: `~/.opencode-delegate/cooldown.json` and `attempts.jsonl` (safe error
  codes only, never the provider's free text).

---

## Group `zen` — OpenCode Zen native  (prefix `opencode/`)

Needs an OpenCode account: `opencode auth login` → **OpenCode**.

| Model | 2026-10-21 | Latency |
|---|---|---|
| `opencode/nemotron-3-ultra-free` | answered correctly | 4.0 s |
| `opencode/nemotron-3.5-lightning-free` | answered correctly | 4.8 s |
| `opencode/nemotron-3.5-super-vl-free` | answered correctly | 4.9 s |
| `opencode/deepseek-v4.1-flash-free` | answered correctly | 6.8 s |
| `opencode/minimax-m3.1-flash-free` | answered correctly | 6.8 s |
| `opencode/longcat-2.5-preview-free` | answered correctly | 7.8 s |
| `opencode/mimo-v2.6-flash-free` | answered correctly | 8.0 s |
| `opencode/glm-5.3-flash-free` | answered correctly | 11.0 s |
| `opencode/beam-free` | answered correctly | 43.1 s |

Known dead (kept out of the fallback order):

- `opencode/big-pickle` — no first event in 45 s (2026-10-21); 0/43 in real use

---

## Group `cline` — Cline free  (prefix `cline/`)

Needs the `cline-free` plugin and `cline auth`. On 2026-10-21 all six answered `Unauthorized: make sure you're using the latest version of Cline` because the login had expired; the auth pause makes that cost one attempt per 30 min instead of one per model.

| Model | 2026-10-21 | Latency |
|---|---|---|
| `cline/cline-free/minimax-m3.1-flash` | login expired | — |
| `cline/cline-free/nemotron-3.5-super-vl` | login expired | — |
| `cline/poolside/laguna-s-2.1-free` | login expired | — |
| `cline/reflection/beam-free` | login expired | — |
| `cline/nvidia/nemotron-3.5-lightning-free` | login expired | — |

---

## Group `pi` — Pi free (NVIDIA NIM)  (prefix `pi-free/`)

Needs the `pi-free-provider` plugin (NVIDIA NIM).

| Model | 2026-10-21 | Latency |
|---|---|---|
| `pi-free/openai/gpt-oss-20b` | answered correctly | 4.0 s |
| `pi-free/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | answered correctly | 4.0 s |
| `pi-free/meta/muse-glimmer-30b` | answered correctly | 28.7 s |

Known dead (kept out of the fallback order):

- `pi-free/moonshotai/kimi-k3` — end of life (2026-10-15)
- `pi-free/minimaxai/minimax-m3` — end of life
- `pi-free/stepfun-ai/step-3.7-flash` — end of life
- `pi-free/nvidia/nemotron-3-nano-30b-a3b` — end of life
- `pi-free/meta/llama-3.2-11b-vision-instruct` — no first event in 45 s
- `pi-free/meta/llama-3.2-90b-vision-instruct` — no first event in 45 s

---

## Group `openkilo` — OpenKilo  (prefix `openkilo/`)

Needs the `openkilo` plugin. Alias: `kilo`.

| Model | 2026-10-21 | Latency |
|---|---|---|
| `openkilo/poolside/laguna-s-2.1:free` | answered correctly | 2.6 s |
| `openkilo/dots-studio/dots-3-note-preview:free` | answered correctly | 3.8 s |
| `openkilo/nvidia/nemotron-3.5-lightning:free` | answered correctly | 4.0 s |
| `openkilo/cohere/north-mini-code:free` | answered correctly | 4.2 s |
| `openkilo/minimax/minimax-m3.1-flash:free` | answered correctly | 4.6 s |
| `openkilo/nvidia/nemotron-3-ultra-550b-a55b:free` | answered correctly | 5.0 s |
| `openkilo/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | answered correctly | 9.6 s |
| `openkilo/poolside/laguna-xs-2.1:free` | answered correctly | 10.2 s |
| `openkilo/stealth/glyph-cluster` | answered correctly | 11.0 s |
| `openkilo/xingchen-agi/xing4.0-29b-a4b:free` | answered correctly | 11.3 s |
| `openkilo/nvidia/nemotron-3.5-super-vl:free` | answered correctly | 13.3 s |
| `openkilo/reflection/beam-free` | answered correctly | 36.3 s |

Known dead (kept out of the fallback order):

- `openkilo/nvidia/nemotron-3-super-120b-a12b:free` — HTTP 404 from provider (2026-10-21)
- `openkilo/liquid/lfm-2.5-2.6b:free` — slow and echoes the system prompt

---

## Group `clixad` — Clixad (optional, via local gateway)  (prefix `thoth/thoth/clixad/`)

Optional. Needs a local OpenAI-compatible gateway registered in `opencode` as provider `thoth` (checked at `OPENCODE_DELEGATE_GATEWAY_URL`). Without it the group is skipped in one step.

| Model | 2026-10-21 | Latency |
|---|---|---|
| `thoth/thoth/clixad/deepseek-v4-flash` | answered correctly | 5.4 s |
| `thoth/thoth/clixad/claude-haiku-5.5` | answered correctly | 5.8 s |
| `thoth/thoth/clixad/gemini-2.5-flash-lite` | answered correctly | 9.1 s |
| `thoth/thoth/clixad/gemini-3.5-flash-lite` | answered correctly | 16.3 s |
