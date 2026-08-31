"""Core delegation logic.

Pick a FREE model from a provider group, run it through the ``opencode`` CLI,
fall back automatically on failure, and remember short/long cooldowns so a
dead model is not retried on every call.

There is no MCP / JSON-RPC in this module — ``server.py`` is the transport
layer. Everything here is plain functions so it can be unit-tested and reused.

Ported from the standalone ``delegate-run.py``.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

DEFAULT_TIMEOUT = 100          # seconds per model attempt
MIN_TIMEOUT = 20
MAX_TIMEOUT = 280
TRANSIENT_COOLDOWN = 300       # 5 min
FATAL_COOLDOWN = 24 * 3600     # 24 h

# Curated, best-first. Only models confirmed live on 2026-08-30.
# This list is the source of truth for fallback order.
GROUPS: dict[str, list[str]] = {
    "zen": [
        "opencode/big-pickle",
        "opencode/mimo-v2.5-free",
        "opencode/laguna-s-2.1-free",
        "opencode/nemotron-3.5-lightning-free",
        "opencode/nemotron-3-ultra-free",
    ],
    "openkilo": [
        "openkilo/minimax/minimax-m3:free",
        "openkilo/minimax/minimax-m2.7:free",
        "openkilo/tencent/hy3:free",
        "openkilo/meituan/longcat-2.0-free",
        "openkilo/inclusionai/ling-3.0-flash-fin:free",
        "openkilo/stepfun/step-3.7-flash:free",
        "openkilo/cohere/north-mini-code:free",
        "openkilo/poolside/laguna-s-2.1:free",
        "openkilo/poolside/laguna-xs-2.1:free",
        "openkilo/dots-studio/dots-3-note-preview:free",
        "openkilo/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "openkilo/nvidia/nemotron-3-super-120b-a12b:free",
        "openkilo/nvidia/nemotron-3.5-lightning:free",
        "openkilo/nvidia/nemotron-3-ultra-550b-a55b:free",
        "openkilo/thinkingmachines/inkling-small:free",
        "openkilo/thinkingmachines/inkling:free",
    ],
    "cline": [
        "cline/z-ai/glm-5.3-flash",
        "cline/deepseek/deepseek-v4-flash",
        "cline/poolside/laguna-s-2.1:free",
        "cline/cline-free/longcat-2.0",
    ],
    "pi": [
        "pi-free/openai/gpt-oss-20b",
        "pi-free/moonshotai/kimi-k3",
        "pi-free/nvidia/nemotron-3-nano-30b-a3b",
        "pi-free/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "pi-free/minimaxai/minimax-m3",
    ],
}
GROUP_PREFIX = {
    "zen": "opencode/",
    "openkilo": "openkilo/",
    "cline": "cline/",
    "pi": "pi-free/",
}

# Probed dead on 2026-08-30 — informational only (list_models surfaces them).
KNOWN_DEAD: dict[str, list[tuple[str, str]]] = {
    "zen": [
        ("opencode/hy3-free", "not supported (removed upstream)"),
        ("opencode/ling-3.0-tiny-free", "not supported (removed upstream)"),
        ("opencode/deepseek-v4-flash-free", "provider reports unavailable"),
    ],
    "openkilo": [
        ("openkilo/google/lyria-3-clip-preview", "needs sign-in; music-gen, not chat"),
        ("openkilo/google/lyria-3-pro-preview", "needs sign-in; music-gen, not chat"),
        ("openkilo/liquid/lfm-2.5-2.6b:free", "ignores the prompt, echoes system text"),
        ("openkilo/nvidia/nemotron-3.5-content-safety:free", "no endpoints support tool use"),
    ],
    "cline": [],
    "pi": [
        ("pi-free/stepfun-ai/step-3.7-flash", "HTTP 410 — end of life 2026-08-28"),
        ("pi-free/meta/llama-3.2-11b-vision-instruct", "rambles, ignores instruction, times out"),
        ("pi-free/meta/llama-3.2-90b-vision-instruct", "rambles, ignores instruction, times out"),
        ("pi-free/meta/muse-glimmer-30b", "times out with no output"),
    ],
}

# Status codes are only read when they look like a status field / HTTP code,
# never as a bare digit run (timestamps contain "410", "500", ...).
_STATUS = r'(?:"?status(?:code)?"?\s*[:=]\s*|http[/ ]\S* )'
FATAL_RE = re.compile(
    r"not supported|end of life|has reached its end|\bgone\b|sign in to use|"
    r"no endpoints found|model not found|" + _STATUS + r"(?:404|410)\b",
    re.I,
)
TRANSIENT_RE = re.compile(
    r"rate.?limit|temporarily|\bunavailable\b|overloaded|\btimeout\b|timed out|"
    r"econnreset|network error|fetch failed|unexpected server error|unknownerror|"
    + _STATUS + r"(?:401|403|408|409|425|429|500|502|503|504)\b",
    re.I,
)


# --------------------------------------------------------------------------- #
# environment / paths
# --------------------------------------------------------------------------- #
def state_dir() -> Path:
    """Where the cooldown file lives. Never inside the plugin directory."""
    override = os.environ.get("OPENCODE_DELEGATE_HOME")
    d = Path(override).expanduser() if override else Path.home() / ".opencode-delegate"
    try:
        d.mkdir(parents=True, exist_ok=True)
        return d
    except Exception:
        return Path(tempfile.gettempdir())


def cooldown_file() -> Path:
    return state_dir() / "cooldown.json"


def resolve_opencode() -> str:
    override = os.environ.get("OPENCODE_DELEGATE_BIN")
    if override and os.path.exists(override):
        return override
    found = shutil.which("opencode") or shutil.which("opencode.cmd")
    if found:
        return found
    for cand in (
        os.path.expandvars(r"%APPDATA%\npm\opencode.cmd"),
        os.path.expandvars(r"%APPDATA%\npm\opencode"),
        os.path.expanduser("~/AppData/Roaming/npm/opencode.cmd"),
        os.path.expanduser("~/.npm-global/bin/opencode"),
        "/usr/local/bin/opencode",
        "/opt/homebrew/bin/opencode",
    ):
        if os.path.exists(cand):
            return cand
    return "opencode"


# --------------------------------------------------------------------------- #
# cooldown persistence
# --------------------------------------------------------------------------- #
def load_cooldown() -> dict[str, float]:
    try:
        with open(cooldown_file(), encoding="utf-8") as fh:
            data = json.load(fh)
        return {k: float(v) for k, v in data.items() if float(v) > time.time()}
    except Exception:
        return {}


def save_cooldown(cd: dict[str, float]) -> None:
    try:
        with open(cooldown_file(), "w", encoding="utf-8") as fh:
            json.dump(cd, fh, indent=0, sort_keys=True)
    except Exception:
        pass  # cooldown is best-effort


# --------------------------------------------------------------------------- #
# model selection
# --------------------------------------------------------------------------- #
def normalize_preferred(group: str, preferred: str) -> str:
    preferred = (preferred or "").strip()
    if not preferred:
        return ""
    pfx = GROUP_PREFIX[group]
    if not preferred.startswith(pfx):
        preferred = pfx + preferred.lstrip("/")
    return preferred


def build_order(group: str, preferred: str = "") -> list[str]:
    order = list(GROUPS[group])
    p = normalize_preferred(group, preferred)
    if p:
        order = [p] + [m for m in order if m != p]
    return order


# --------------------------------------------------------------------------- #
# running one model through opencode
# --------------------------------------------------------------------------- #
def extract_text(raw: str) -> str:
    parts: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except Exception:
            continue
        if evt.get("type") == "text":
            part = evt.get("part") or {}
            parts.append(part.get("text") or evt.get("text") or "")
    return "".join(parts).strip()


def first_error(blob: str) -> str:
    for line in blob.splitlines():
        if re.search(r"error|unavailable|rate|gone|not supported|not found", line, re.I):
            return line.strip()[:300]
    return ""


def classify(diag: str) -> int:
    if FATAL_RE.search(diag):
        return FATAL_COOLDOWN
    if TRANSIENT_RE.search(diag) or "no text" in diag or "timeout" in diag:
        return TRANSIENT_COOLDOWN
    return TRANSIENT_COOLDOWN  # unknown -> treat as transient


def run_one(model: str, prompt: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[bool, str, str]:
    """Return (ok, answer_text, diagnostic)."""
    opencode = resolve_opencode()
    try:
        proc = subprocess.run(
            [opencode, "run", "-m", model, "--format", "json", prompt],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "", f"timeout after {timeout}s"
    except FileNotFoundError:
        return False, "", "opencode CLI not found on PATH (set OPENCODE_DELEGATE_BIN)"
    blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
    text = extract_text(proc.stdout or "")
    if proc.returncode == 0 and text:
        if re.search(r'"type"\s*:\s*"error"', proc.stdout or ""):
            return False, "", first_error(blob)
        return True, text, ""
    return False, "", first_error(blob) or f"exit {proc.returncode}, no text"


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def delegate(group: str, prompt: str, preferred: str = "",
             timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Try the group's models best-first with fallback + cooldown.

    Returns a dict:
      ok=True  -> group, model, attempt, answer, skipped[], failures[]
      ok=False -> error, plus (group, tried[], skipped[], failures[]) when
                  the whole group is exhausted.
    """
    group = (group or "").strip().lower()
    if group not in GROUPS:
        return {"ok": False, "error": f"unknown group '{group}'",
                "groups": list(GROUPS)}
    if not (prompt or "").strip():
        return {"ok": False, "error": "empty prompt"}

    try:
        timeout = int(timeout or DEFAULT_TIMEOUT)
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT
    timeout = max(MIN_TIMEOUT, min(MAX_TIMEOUT, timeout))

    order = build_order(group, preferred)
    cd = load_cooldown()
    tried: list[str] = []
    skipped: list[dict] = []
    failures: list[dict] = []

    for attempt, model in enumerate(order, 1):
        if model in cd:
            mins = int((cd[model] - time.time()) / 60) + 1
            skipped.append({"model": model, "cooling_minutes": mins})
            continue
        tried.append(model)
        ok, text, diag = run_one(model, prompt, timeout)
        if ok:
            save_cooldown(cd)
            return {"ok": True, "group": group, "model": model,
                    "attempt": attempt, "answer": text,
                    "skipped": skipped, "failures": failures}
        secs = classify(diag)
        cd[model] = time.time() + secs
        failures.append({"model": model, "diagnostic": diag or "unknown",
                         "cooldown_seconds": secs})

    save_cooldown(cd)
    return {"ok": False, "error": "group exhausted", "group": group,
            "tried": tried, "skipped": skipped, "failures": failures}
