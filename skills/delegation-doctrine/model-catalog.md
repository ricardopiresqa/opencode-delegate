# Free-model catalogue

Models reachable through the `opencode` CLI, grouped by provider plugin. Use
this to decide **whether** and **where** to delegate a low-complexity task.

Discovered and probed **2026-08-30** with `opencode models --refresh` plus one
minimal live call per model (`opencode run -m <id> --format json "reply only: ok"`).
All probe calls were `$0` on these free tiers. Re-probe with
`opencode models --refresh` if a model starts erroring — free tiers change.

The fallback **order** is defined in `mcp/core.py` (`GROUPS`); this document is
the human-readable rationale.

## Fallback & cooldown (how the `delegate` tool behaves)

- tries the group's models best-first (your `preferred_model` first, if given);
- skips any model currently in cooldown;
- transient failure (rate limit / temporary / timeout / network) → 5-minute
  cooldown on that model, try the next;
- fatal failure (retired / not supported / needs sign-in / 404 / 410) →
  24-hour cooldown so the session stops trying it;
- returns the winning model's text + `>>> answered by <group>/<model>`;
- errors only when every model in the group is down or cooling.

Cooldown state persists at `~/.opencode-delegate/cooldown.json` (override the
directory with `OPENCODE_DELEGATE_HOME`).

Note: `opencode` loads a large steering system prompt on startup, so each
delegated call carries a big fixed input (cost `$0` on these free models, but
a few seconds of latency). Worth it when it saves real orchestrator reasoning;
not worth it for a one-word answer you already know.

---

## Group `zen` — OpenCode Zen native  (prefix `opencode/`)

Needs an OpenCode account: `opencode auth login` → **OpenCode**.

| Model | Status | ~Latency | Recommended use |
|---|---|---|---|
| `opencode/big-pickle` | OK | ~15s | Strongest generalist in the group. Nuanced classification, rewrite, light-judgement summary. **Group default.** |
| `opencode/mimo-v2.5-free` | OK | ~20s | Generalist. Summaries, extraction, reformatting. |
| `opencode/laguna-s-2.1-free` | OK | ~15s | Code (poolside). Boilerplate, mechanical refactor, simple test scaffolding, syntax conversion. |
| `opencode/nemotron-3.5-lightning-free` | OK | ~50s | NVIDIA throughput. Batch classification / triage of many short items. |
| `opencode/nemotron-3-ultra-free` | OK | ~90s | Large, slow. Delegable tasks needing a bit more reasoning when latency is irrelevant. |
| `opencode/hy3-free` | DEAD | — | "not supported" (removed upstream). |
| `opencode/ling-3.0-tiny-free` | DEAD | — | "not supported" (removed upstream). |
| `opencode/deepseek-v4-flash-free` | DEAD | — | provider reports "unavailable". |

Working: **5 / 8**.

---

## Group `openkilo` — OpenKilo  (prefix `openkilo/`)

Needs the `openkilo` opencode plugin. See its README for setup/auth.

| Model | Status | ~Latency | Recommended use |
|---|---|---|---|
| `openkilo/minimax/minimax-m3:free` | OK | ~10s | Fast generalist. Summaries, extraction, reformatting. **Group default.** |
| `openkilo/minimax/minimax-m2.7:free` | OK | ~12s | Generalist (older sibling of m3). |
| `openkilo/tencent/hy3:free` | OK | ~19s | Solid generalist. |
| `openkilo/meituan/longcat-2.0-free` | OK | ~12s | Generalist text. |
| `openkilo/inclusionai/ling-3.0-flash-fin:free` | OK | ~14s | "Flash". Bulk classification / triage. |
| `openkilo/stepfun/step-3.7-flash:free` | OK | ~16s | Flash. Short summaries, formatting, field extraction. |
| `openkilo/cohere/north-mini-code:free` | OK | ~13s | Small code model. Snippets, syntax conversion, boilerplate. |
| `openkilo/poolside/laguna-s-2.1:free` | OK | ~13s | Code. Mechanical refactor, test scaffolding. |
| `openkilo/poolside/laguna-xs-2.1:free` | OK | ~10s | Smallest / fastest. Yes-no, binary classification, one-line lookups. Rate-limits first under load. |
| `openkilo/dots-studio/dots-3-note-preview:free` | OK | ~12s | Note / structure oriented. Structured summaries, bullet / outline extraction. |
| `openkilo/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | OK | ~13s | Nano + reasoning. Small multi-step logic, classification with rationale. Accepts images. |
| `openkilo/nvidia/nemotron-3-super-120b-a12b:free` | OK | ~12s | Mid-large. A notch above the nanos. |
| `openkilo/nvidia/nemotron-3.5-lightning:free` | OK | ~45s | Throughput. Batch triage. |
| `openkilo/nvidia/nemotron-3-ultra-550b-a55b:free` | OK | ~30s | Largest here. Best in-group quality for a harder-but-delegable task. |
| `openkilo/thinkingmachines/inkling-small:free` | OK | ~11s | Small. Query rephrasing, intent tags, light classification. |
| `openkilo/thinkingmachines/inkling:free` | OK ⚠ | ~10s | Small-mid. Verbose; follows ambient system instructions — needs a very explicit, self-contained prompt. Last-resort. |
| `openkilo/google/lyria-3-clip-preview` | DEAD | — | needs sign-in; music generation, not chat. |
| `openkilo/google/lyria-3-pro-preview` | DEAD | — | same as above. |
| `openkilo/liquid/lfm-2.5-2.6b:free` | DEAD | — | ignores the prompt, echoes system text, times out. |
| `openkilo/nvidia/nemotron-3.5-content-safety:free` | DEAD | — | "no endpoints found that support tool use" — cannot run under `opencode run`. |

Working: **16 / 20**.

---

## Group `cline` — Cline recommended free  (prefix `cline/`)

Needs the `cline-free` opencode plugin and a Cline login (`cline auth`). The
list is fetched live from Cline's recommended-models endpoint; run
`opencode models` to refresh. An expired session shows as "run `cline auth`".

| Model | Status | ~Latency | Recommended use |
|---|---|---|---|
| `cline/z-ai/glm-5.3-flash` | OK | ~19s | GLM flash. Fast generalist — summary, classification, rewrite. **Group default.** |
| `cline/deepseek/deepseek-v4-flash` | OK | ~16s | DeepSeek flash. Good code + generalist balance; extraction, small transforms. |
| `cline/poolside/laguna-s-2.1:free` | OK | ~12s | Code. Boilerplate, mechanical refactor, test scaffolding. |
| `cline/cline-free/longcat-2.0` | OK | ~38s | Generalist, slower. Text tasks where latency is not a concern. |

Working: **4 / 4**. No known-dead entries.

---

## Group `pi` — Pi free  (prefix `pi-free/`)

Needs the `pi-free-provider` opencode plugin (served over NVIDIA NIM). See its
README for setup.

| Model | Status | ~Latency | Recommended use |
|---|---|---|---|
| `pi-free/openai/gpt-oss-20b` | OK | ~9s | Fastest. Reasoning-capable. Classification, triage, structured extraction, small JSON. **Group default.** |
| `pi-free/moonshotai/kimi-k3` | OK | ~10s | Reasoning, ~1M context. Summarising long text, lookup in a large document. |
| `pi-free/nvidia/nemotron-3-nano-30b-a3b` | OK | ~12s | Nano + reasoning. Short logic steps, classification with rationale. |
| `pi-free/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | OK | ~13s | Nano omni + reasoning. As above; also accepts image input. |
| `pi-free/minimaxai/minimax-m3` | OK | ~50s | Slow here. ~1M context, reasoning. Only for very long material when latency does not matter. |
| `pi-free/stepfun-ai/step-3.7-flash` | DEAD | — | HTTP 410 — end of life 2026-08-28. |
| `pi-free/meta/llama-3.2-11b-vision-instruct` | DEAD | — | ignores the instruction, rambles, times out. |
| `pi-free/meta/llama-3.2-90b-vision-instruct` | DEAD | — | same — rambles, times out. |
| `pi-free/meta/muse-glimmer-30b` | DEAD | — | times out with no output. |

Working: **5 / 9**.

---

## Totals

| Group | Working | Tested |
|---|---|---|
| `zen` — OpenCode Zen native (`opencode/`) | 5 | 8 |
| `openkilo` — OpenKilo (`openkilo/`) | 16 | 20 |
| `cline` — Cline free (`cline/`) | 4 | 4 |
| `pi` — Pi free (`pi-free/`) | 5 | 9 |
| **All** | **30** | **41** |
