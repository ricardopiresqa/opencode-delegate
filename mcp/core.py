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
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_TIMEOUT = 100          # seconds per model attempt (consult mode)
APPLY_TIMEOUT = 240            # default per-attempt timeout when apply=True
MIN_TIMEOUT = 20
MAX_TIMEOUT = 600
TRANSIENT_COOLDOWN = 300       # 5 min
FATAL_COOLDOWN = 24 * 3600     # 24 h
# Pauses are persisted in the cooldown file under "group:<g>" / "provider:<p>" so a
# provider that is down is skipped in ONE step on the next call too, instead of
# paying one failed attempt per model on every call.
GROUP_FAILURES_TO_PAUSE = 3    # consecutive failures in a group -> pause the group
GROUP_PAUSE = 900              # 15 min
AUTH_PAUSE = 1800              # 401/403/unauthorized: the login belongs to the provider
GATEWAY_DOWN_PAUSE = 600       # optional local gateway (provider "thoth") not answering
GATEWAY_PROVIDER = "thoth"
GATEWAY_URL = os.environ.get("OPENCODE_DELEGATE_GATEWAY_URL", "http://127.0.0.1:11435/v1/models")
# Auto-quarantine: the model's last N real attempts inside the window all failed.
# One success (a probe counts) releases it. Launch failures do not count.
AUTO_QUARANTINE_RUN = 10
AUTO_QUARANTINE_DAYS = 7

# Curated, best-first (fastest first). Probed on 2026-10-21: each model had to
# answer "OK" and 17*23-45 correctly. This list is the source of truth for
# fallback order.
GROUPS: dict[str, list[str]] = {
    "zen": [
        "opencode/nemotron-3-ultra-free",
        "opencode/nemotron-3.5-lightning-free",
        "opencode/nemotron-3.5-super-vl-free",
        "opencode/deepseek-v4.1-flash-free",
        "opencode/minimax-m3.1-flash-free",
        "opencode/longcat-2.5-preview-free",
        "opencode/mimo-v2.6-flash-free",
        "opencode/glm-5.3-flash-free",
        "opencode/beam-free",
    ],
    "cline": [
        "cline/cline-free/minimax-m3.1-flash",
        "cline/cline-free/nemotron-3.5-super-vl",
        "cline/poolside/laguna-s-2.1-free",
        "cline/reflection/beam-free",
        "cline/nvidia/nemotron-3.5-lightning-free",
    ],
    "pi": [
        "pi-free/openai/gpt-oss-20b",
        "pi-free/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "pi-free/meta/muse-glimmer-30b",
    ],
    "openkilo": [
        "openkilo/poolside/laguna-s-2.1:free",
        "openkilo/dots-studio/dots-3-note-preview:free",
        "openkilo/nvidia/nemotron-3.5-lightning:free",
        "openkilo/cohere/north-mini-code:free",
        "openkilo/minimax/minimax-m3.1-flash:free",
        "openkilo/nvidia/nemotron-3-ultra-550b-a55b:free",
        "openkilo/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "openkilo/poolside/laguna-xs-2.1:free",
        "openkilo/stealth/glyph-cluster",
        "openkilo/xingchen-agi/xing4.0-29b-a4b:free",
        "openkilo/nvidia/nemotron-3.5-super-vl:free",
        "openkilo/reflection/beam-free",
    ],
    # Optional: Clixad through a local OpenAI-compatible gateway registered in
    # opencode as provider "thoth" (see README). Without it the group is skipped
    # in one step (gateway check) and never costs a model attempt.
    "clixad": [
        "thoth/thoth/clixad/deepseek-v4-flash",
        "thoth/thoth/clixad/claude-haiku-5.5",
        "thoth/thoth/clixad/gemini-2.5-flash-lite",
        "thoth/thoth/clixad/gemini-3.5-flash-lite",
    ],
}
GROUP_PREFIX = {
    "zen": "opencode/",
    "cline": "cline/",
    "pi": "pi-free/",
    "openkilo": "openkilo/",
    "clixad": "thoth/thoth/clixad/",
}
# Accepted alternative names (people say "kilo" and "opencode").
GROUP_ALIASES = {"kilo": "openkilo", "opencode": "zen"}

# Probed dead — informational only (list_models surfaces them).
KNOWN_DEAD: dict[str, list[tuple[str, str]]] = {
    "zen": [
        ("opencode/big-pickle", "no first event in 45 s (2026-10-21); 0/43 in real use"),
    ],
    "openkilo": [
        ("openkilo/nvidia/nemotron-3-super-120b-a12b:free", "HTTP 404 from provider (2026-10-21)"),
        ("openkilo/liquid/lfm-2.5-2.6b:free", "slow and echoes the system prompt"),
    ],
    "cline": [],
    "pi": [
        ("pi-free/moonshotai/kimi-k3", "end of life (2026-10-15)"),
        ("pi-free/minimaxai/minimax-m3", "end of life"),
        ("pi-free/stepfun-ai/step-3.7-flash", "end of life"),
        ("pi-free/nvidia/nemotron-3-nano-30b-a3b", "end of life"),
        ("pi-free/meta/llama-3.2-11b-vision-instruct", "no first event in 45 s"),
        ("pi-free/meta/llama-3.2-90b-vision-instruct", "no first event in 45 s"),
    ],
    "clixad": [],
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


def attempts_file() -> Path:
    return state_dir() / "attempts.jsonl"


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
    # tmp + os.replace: a process killed mid-write must not leave truncated JSON,
    # which load_cooldown() would read as "no cooldowns at all".
    target = cooldown_file()
    tmp = target.with_name(target.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cd, fh, indent=0, sort_keys=True)
        os.replace(tmp, target)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass  # cooldown is best-effort


# --------------------------------------------------------------------------- #
# model selection
# --------------------------------------------------------------------------- #
def resolve_group(group: str) -> str:
    group = (group or "").strip().lower()
    return GROUP_ALIASES.get(group, group)


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


def attempt_kind(ok: bool, diag: str) -> str:
    """Short category of an attempt."""
    if ok:
        return "ok"
    low = (diag or "").lower()
    if "timeout" in low or "timed out" in low:
        return "timeout"
    if re.search(r"\b429\b|rate.?limit|\bquota\b", low):
        return "rate_limit"
    if re.search(r"\b40[13]\b|unauthorized|forbidden", low):
        return "auth"
    if "not found" in low or "unavailable" in low or "end of life" in low or "gone" in low:
        return "unavailable"
    if "no text" in low:
        return "empty"
    return "error"


ERROR_LABELS = ("unauthorized", "forbidden", "rate limit", "quota", "model not found", "not supported",
                "end of life", "gone", "no endpoints", "overloaded", "unavailable", "econnrefused",
                "econnreset", "fetch failed", "network error", "no text", "timeout")


def error_code(diag: str) -> str:
    """Safe error signature: an HTTP status plus labels from a CLOSED list.

    Never free text: provider errors can quote the prompt, and the log lives on disk.
    """
    low = (diag or "").lower()
    status = re.findall(_STATUS + r"(\d{3})\b", low, re.I) or re.findall(r"\b([45]\d\d)\b", low)
    labels = [label for label in ERROR_LABELS if label in low]
    return " ".join(([status[0]] if status else []) + labels)[:80]


def record_attempt(model: str, ok: bool, diag: str, seconds: float, source: str = "delegate") -> None:
    """Append one line per attempt (best-effort; never breaks a delegation)."""
    item = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": source,
            "model": model, "ok": ok, "kind": attempt_kind(ok, diag), "seconds": round(seconds, 2)}
    if not ok:
        item["code"] = error_code(diag)
    try:
        with open(attempts_file(), "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(item) + "\n")
    except Exception:
        pass


def auto_quarantine(path: str = "") -> dict[str, str]:
    """Models whose last AUTO_QUARANTINE_RUN attempts inside the window all failed."""
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - AUTO_QUARANTINE_DAYS * 86400))
    runs: dict[str, list[bool]] = {}
    try:
        with open(path or attempts_file(), encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("ts", "") >= cutoff and row.get("kind") != "launch" and row.get("model"):
                    runs.setdefault(row["model"], []).append(bool(row.get("ok")))
    except OSError:
        return {}
    return {m: f"auto: last {AUTO_QUARANTINE_RUN} attempts failed" for m, oks in runs.items()
            if len(oks) >= AUTO_QUARANTINE_RUN and not any(oks[-AUTO_QUARANTINE_RUN:])}


def gateway_up() -> bool:
    """Does the optional local gateway answer? Any HTTP answer (even 401) means up."""
    if not GATEWAY_URL.lower().startswith(("http://", "https://")):
        return False  # only plain HTTP(S) health checks; never file:// or other schemes
    try:
        urllib.request.urlopen(GATEWAY_URL, timeout=2).close()
        return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError):
        return False


def pause_left(cd: dict[str, float], key: str) -> int:
    """Minutes left on a persisted pause (0 = none)."""
    return max(0, int((cd[key] - time.time()) / 60) + 1) if cd.get(key, 0) > time.time() else 0


def build_cmd(opencode: str, model: str, prompt: str, apply: bool = False) -> list[str]:
    """argv for one ``opencode run``.

    consult (default): read-only relay, the text answer is the product.
    apply=True: add ``--auto`` so the model may edit files in the working directory
    without a per-tool prompt; the changed tree is the product and the text is a summary.
    """
    cmd = [opencode, "run", "-m", model, "--format", "json"]
    if apply:
        cmd.append("--auto")
    cmd.append(prompt)
    return cmd


def run_one(model: str, prompt: str, timeout: int = DEFAULT_TIMEOUT,
            apply: bool = False, cwd: str = "") -> tuple[bool, str, str]:
    """Return (ok, answer_text, diagnostic).

    With ``apply=True`` the model runs with ``--auto`` in ``cwd`` and may edit files;
    success then no longer requires non-empty text (the diff is the result).
    """
    opencode = resolve_opencode()
    workdir = cwd or None
    if workdir and not os.path.isdir(workdir):
        return False, "", f"cwd does not exist: {workdir}"
    try:
        proc = subprocess.run(
            build_cmd(opencode, model, prompt, apply),
            capture_output=True, text=True, timeout=timeout, cwd=workdir,
        )
    except subprocess.TimeoutExpired:
        return False, "", f"timeout after {timeout}s"
    except FileNotFoundError:
        return False, "", "opencode CLI not found on PATH (set OPENCODE_DELEGATE_BIN)"
    blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
    text = extract_text(proc.stdout or "")
    if proc.returncode == 0 and (text or apply):
        if re.search(r'"type"\s*:\s*"error"', proc.stdout or ""):
            return False, "", first_error(blob)
        return True, text or "(apply mode: no summary text returned; review the working-tree diff)", ""
    return False, "", first_error(blob) or f"exit {proc.returncode}, no text"


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def delegate(group: str, prompt: str, preferred: str = "",
             timeout: int = DEFAULT_TIMEOUT, apply: bool = False,
             cwd: str = "") -> dict:
    """Try the group's models best-first with fallback + cooldown.

    ``apply=True`` runs the winning model with ``--auto`` in ``cwd`` so it can edit
    files directly (BUILD mode); the return then also carries ``applied`` and ``cwd``.
    Timeout defaults to ``APPLY_TIMEOUT`` in that mode.

    Returns a dict:
      ok=True  -> group, model, attempt, answer, applied, cwd, skipped[], failures[]
      ok=False -> error, plus (group, tried[], skipped[], failures[]) when
                  the whole group is exhausted.
    """
    group = resolve_group(group)
    if group not in GROUPS:
        return {"ok": False, "error": f"unknown group '{group}'",
                "groups": list(GROUPS)}
    if not (prompt or "").strip():
        return {"ok": False, "error": "empty prompt"}

    apply = bool(apply)
    default_timeout = APPLY_TIMEOUT if apply else DEFAULT_TIMEOUT
    try:
        timeout = int(timeout or default_timeout)
    except (TypeError, ValueError):
        timeout = default_timeout
    timeout = max(MIN_TIMEOUT, min(MAX_TIMEOUT, timeout))

    order = build_order(group, preferred)
    explicit = normalize_preferred(group, preferred)
    cd = load_cooldown()
    quarantined = auto_quarantine()
    tried: list[str] = []
    skipped: list[dict] = []
    failures: list[dict] = []
    streak = 0
    gateway: bool | None = None

    for attempt, model in enumerate(order, 1):
        provider = model.split("/", 1)[0]
        if model != explicit:
            mins = pause_left(cd, f"provider:{provider}") or pause_left(cd, f"group:{group}")
            if mins:
                skipped.append({"model": model, "paused_minutes": mins})
                continue
            if model in quarantined:
                skipped.append({"model": model, "quarantined": quarantined[model]})
                continue
        if provider == GATEWAY_PROVIDER:
            gateway = gateway_up() if gateway is None else gateway
            if not gateway:
                cd[f"provider:{provider}"] = time.time() + GATEWAY_DOWN_PAUSE
                skipped.append({"model": model, "gateway_down": GATEWAY_URL})
                continue
        if model in cd:
            mins = int((cd[model] - time.time()) / 60) + 1
            skipped.append({"model": model, "cooling_minutes": mins})
            continue
        tried.append(model)
        started = time.monotonic()
        ok, text, diag = run_one(model, prompt, timeout, apply=apply, cwd=cwd)
        record_attempt(model, ok, diag, time.monotonic() - started)
        if ok:
            save_cooldown(cd)
            return {"ok": True, "group": group, "model": model,
                    "attempt": attempt, "answer": text,
                    "applied": apply, "cwd": cwd or os.getcwd(),
                    "skipped": skipped, "failures": failures}
        secs = classify(diag)
        cd[model] = time.time() + secs
        streak += 1
        if attempt_kind(False, diag) == "auth":
            cd[f"provider:{provider}"] = time.time() + AUTH_PAUSE
        if streak >= GROUP_FAILURES_TO_PAUSE:
            cd[f"group:{group}"] = time.time() + GROUP_PAUSE
        failures.append({"model": model, "diagnostic": diag or "unknown",
                         "cooldown_seconds": secs})

    save_cooldown(cd)
    return {"ok": False, "error": "group exhausted", "group": group,
            "tried": tried, "skipped": skipped, "failures": failures}
