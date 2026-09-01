#!/usr/bin/env python3
"""Minimal MCP stdio server exposing the opencode-delegate tools.

Speaks JSON-RPC 2.0 over stdin/stdout, one JSON object per line (the MCP
stdio framing). Zero third-party dependencies — standard library only,
Python 3.8+.

Tools:
  delegate      run a prompt on a free model from a provider group
  list_models   curated live model list per group (fallback order)
  catalog       full human-readable catalogue with per-model status
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402

SERVER_NAME = "opencode-delegate"
VERSION = "0.2.0"
PROTOCOL = "2024-11-05"

CATALOG_FILE = (
    Path(__file__).resolve().parent.parent
    / "skills" / "delegation-doctrine" / "model-catalog.md"
)

TOOLS = [
    {
        "name": "delegate",
        "description": (
            "Run a task on a FREE model from an opencode provider group, with "
            "automatic in-group fallback and cooldown. The model computation costs "
            "no Claude tokens. Good for classification, triage, short summaries, "
            "field extraction, mechanical reformatting, boilerplate, and trivial "
            "lookups — especially at volume. With apply=true the model runs in "
            "BUILD mode (--auto) and may EDIT FILES in cwd directly; use that only "
            "for a mechanical, well-scoped change, and review the diff after. Do "
            "NOT delegate architecture, security, or risk judgement, or deep "
            "reasoning, in either mode."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "group": {
                    "type": "string",
                    "enum": ["zen", "openkilo", "cline", "pi"],
                    "description": (
                        "Provider group. zen=OpenCode Zen native, "
                        "openkilo=OpenKilo, cline=Cline recommended, pi=Pi free."
                    ),
                },
                "prompt": {
                    "type": "string",
                    "description": "Self-contained task text for the model.",
                },
                "preferred_model": {
                    "type": "string",
                    "description": (
                        "Optional model id to try first (group prefix optional). "
                        "Omit to start from the top of the group."
                    ),
                },
                "timeout_s": {
                    "type": "integer",
                    "minimum": 20,
                    "maximum": 600,
                    "description": (
                        "Per-attempt timeout in seconds (default 100 consult, "
                        "240 when apply=true)."
                    ),
                },
                "apply": {
                    "type": "boolean",
                    "description": (
                        "BUILD mode: run the model with --auto so it edits files "
                        "in cwd directly. Default false (read-only relay). Only for "
                        "a mechanical, well-scoped change; review the diff after."
                    ),
                },
                "cwd": {
                    "type": "string",
                    "description": (
                        "Working directory for apply mode (the repo/subtree the "
                        "model may edit). Defaults to the server's current dir."
                    ),
                },
            },
            "required": ["group", "prompt"],
        },
    },
    {
        "name": "list_models",
        "description": (
            "List the curated live free models per group (the source of truth "
            "for fallback order), plus known-dead entries the runner skips."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "group": {
                    "type": "string",
                    "enum": ["zen", "openkilo", "cline", "pi"],
                    "description": "Restrict to one group. Omit for all.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "catalog",
        "description": (
            "Return the full human-readable model catalogue: per-model status, "
            "latency, and recommended use for every group."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


# --------------------------------------------------------------------------- #
# tool handlers -> MCP tool result ({content:[...], isError:bool})
# --------------------------------------------------------------------------- #
def _text_result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def tool_delegate(args: dict) -> dict:
    apply = bool(args.get("apply", False))
    r = core.delegate(
        args.get("group", ""),
        args.get("prompt", ""),
        args.get("preferred_model", ""),
        args.get("timeout_s", core.APPLY_TIMEOUT if apply else core.DEFAULT_TIMEOUT),
        apply=apply,
        cwd=args.get("cwd", ""),
    )
    if r.get("ok"):
        foot = f">>> answered by {r['model']} (attempt {r['attempt']})"
        notes = []
        if r.get("applied"):
            notes.append(
                f"BUILD mode: files may have been modified in {r.get('cwd')} "
                f"— review the diff (e.g. `git -C {r.get('cwd')} status`)."
            )
        for s in r.get("skipped", []):
            notes.append(f"skipped (cooling ~{s['cooling_minutes']}m): {s['model']}")
        for f in r.get("failures", []):
            notes.append(
                f"fell back from {f['model']}: {f['diagnostic']} "
                f"(cooldown {f['cooldown_seconds'] // 60}m)"
            )
        text = r["answer"] + "\n\n---\n" + foot
        if notes:
            text += "\n" + "\n".join(notes)
        return _text_result(text)

    if r.get("error") == "group exhausted":
        msg = [
            f"Group '{r['group']}' is exhausted — every model is down or cooling.",
            f"Tried: {', '.join(r.get('tried') or []) or '(none, all cooling)'}",
        ]
        for f in r.get("failures", []):
            msg.append(f"  - {f['model']}: {f['diagnostic']}")
        for s in r.get("skipped", []):
            msg.append(f"  - {s['model']}: cooling ~{s['cooling_minutes']}m")
        msg.append("Try another group (zen|openkilo|cline|pi) or handle it yourself.")
        return _text_result("\n".join(msg), is_error=True)

    return _text_result(r.get("error", "delegation failed"), is_error=True)


def tool_list_models(args: dict) -> dict:
    g = (args.get("group") or "").strip().lower()
    groups = [g] if g in core.GROUPS else list(core.GROUPS)
    lines: list[str] = []
    for name in groups:
        lines.append(f"## {name}  (prefix {core.GROUP_PREFIX[name]})")
        for m in core.GROUPS[name]:
            lines.append(f"  - {m}")
        for m, why in core.KNOWN_DEAD.get(name, []):
            lines.append(f"  - [dead] {m} — {why}")
        lines.append("")
    return _text_result("\n".join(lines).strip())


def tool_catalog(args: dict) -> dict:
    try:
        return _text_result(CATALOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _text_result(
            "Catalogue file not found. Live fallback order:\n"
            + json.dumps(core.GROUPS, indent=2)
        )


HANDLERS = {
    "delegate": tool_delegate,
    "list_models": tool_list_models,
    "catalog": tool_catalog,
}


# --------------------------------------------------------------------------- #
# JSON-RPC plumbing
# --------------------------------------------------------------------------- #
def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def reply(mid, result: dict) -> None:
    send({"jsonrpc": "2.0", "id": mid, "result": result})


def error(mid, code: int, message: str) -> None:
    send({"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}})


def handle(msg: dict) -> None:
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}

    if method == "initialize":
        reply(mid, {
            "protocolVersion": params.get("protocolVersion") or PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": VERSION},
        })
    elif method in ("notifications/initialized", "initialized"):
        return  # notification, no response
    elif method == "ping":
        reply(mid, {})
    elif method == "tools/list":
        reply(mid, {"tools": TOOLS})
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        fn = HANDLERS.get(name)
        if fn is None:
            error(mid, -32602, f"unknown tool: {name}")
            return
        try:
            reply(mid, fn(args))
        except Exception as exc:  # never crash the server on a bad call
            reply(mid, _text_result(f"tool error: {exc}", is_error=True))
    elif mid is not None:
        error(mid, -32601, f"method not found: {method}")
    # unknown notification (no id) -> ignore


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if isinstance(msg, dict):
            handle(msg)
        elif isinstance(msg, list):  # JSON-RPC batch
            for item in msg:
                if isinstance(item, dict):
                    handle(item)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, BrokenPipeError):
        pass
