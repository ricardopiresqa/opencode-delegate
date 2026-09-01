#!/usr/bin/env python3
"""Offline unit checks for mcp/core.py — no opencode CLI, no network.

Run:  python3 tests/test_core.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))
import core  # noqa: E402

_fails = 0


def check(name: str, cond: bool) -> None:
    global _fails
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        _fails += 1


check("every group has models", all(core.GROUPS.values()))

check(
    "every model carries its group prefix",
    all(
        m.startswith(core.GROUP_PREFIX[g])
        for g, ms in core.GROUPS.items()
        for m in ms
    ),
)

check(
    "a timestamp containing 410 is treated as transient, not fatal",
    core.classify("fetch failed at 1788141049338") == core.TRANSIENT_COOLDOWN,
)

check(
    "a real HTTP 410 is fatal",
    core.classify('{"error":{"statusCode":410,"message":"gone"}}') == core.FATAL_COOLDOWN,
)

check(
    'a "status": 429 is transient',
    core.classify('provider returned "status": 429') == core.TRANSIENT_COOLDOWN,
)

check(
    '"model not supported" is fatal',
    core.classify("Error: model is not supported") == core.FATAL_COOLDOWN,
)

check(
    "preferred model gets the group prefix added",
    core.normalize_preferred("pi", "openai/gpt-oss-20b") == "pi-free/openai/gpt-oss-20b",
)

check(
    "already-prefixed preferred model is left alone",
    core.normalize_preferred("openkilo", "openkilo/minimax/minimax-m3:free")
    == "openkilo/minimax/minimax-m3:free",
)

check(
    "build_order puts the preferred model first",
    core.build_order("zen", "mimo-v2.5-free")[0] == "opencode/mimo-v2.5-free",
)

check(
    "build_order without preferred keeps curated order",
    core.build_order("cline") == core.GROUPS["cline"],
)

check(
    "extract_text concatenates text events (part.text and top-level text)",
    core.extract_text(
        '{"type":"text","part":{"text":"4"}}\n{"type":"text","text":"2"}'
    )
    == "42",
)

check(
    "delegate rejects an unknown group without calling anything",
    core.delegate("bogus", "hi")["ok"] is False,
)

check(
    "delegate rejects an empty prompt",
    core.delegate("zen", "   ")["ok"] is False,
)

check(
    "build_cmd consult mode: no --auto, prompt is the last argv",
    core.build_cmd("opencode", "opencode/big-pickle", "hello")
    == ["opencode", "run", "-m", "opencode/big-pickle", "--format", "json", "hello"],
)

check(
    "build_cmd apply mode: --auto before the prompt",
    core.build_cmd("opencode", "opencode/big-pickle", "hello", apply=True)
    == ["opencode", "run", "-m", "opencode/big-pickle", "--format", "json", "--auto", "hello"],
)

check(
    "run_one apply mode with a non-existent cwd fails fast without spawning",
    core.run_one("opencode/big-pickle", "hi", apply=True, cwd="/no/such/dir/xyz")
    == (False, "", "cwd does not exist: /no/such/dir/xyz"),
)

check(
    "delegate still validates group/prompt when apply=True",
    core.delegate("bogus", "hi", apply=True)["ok"] is False
    and core.delegate("zen", "  ", apply=True)["ok"] is False,
)

check(
    "APPLY_TIMEOUT is defined and within the clamp range",
    core.MIN_TIMEOUT <= core.APPLY_TIMEOUT <= core.MAX_TIMEOUT,
)

print()
if _fails:
    print(f"{_fails} check(s) failed")
    sys.exit(1)
print("all checks passed")
