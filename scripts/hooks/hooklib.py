"""Shared helpers for the Maestro hooks. Standard library only; never raises to the caller."""

import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

LRI, PDI = chr(0x2066), chr(0x2069)  # keep numbers left-to-right inside Arabic text
LOG_LIMIT = 200
RETRIES = 3
RETRY_DELAY = 0.5
MANIFEST = (".claude-plugin", "plugin.json")


def ltr(value):
    return f"{LRI}{value}{PDI}"


def hooks_dir():
    return Path(__file__).resolve().parent


def scripts_dir():
    return hooks_dir().parent


def ledger_cmd():
    """The command that runs this install's ledger.py, with its real absolute path."""
    return f'python3 "{scripts_dir() / "ledger.py"}"'


def manifest_path(scripts=None):
    return Path(scripts or scripts_dir()).parent.joinpath(*MANIFEST)


def is_plugin_layout(scripts=None):
    """True when scripts/ sits next to .claude-plugin/plugin.json (installed as the plugin)."""
    return manifest_path(scripts).is_file()


def data_dir(project=None, scripts=None):
    """Where learning files live: MAESTRO_HOME, else ~/.claude/maestro (plugin), else <project>/.claude/conductor."""
    env = os.environ.get("MAESTRO_HOME")
    if env:
        return Path(env).expanduser()
    if is_plugin_layout(scripts):
        return Path.home() / ".claude" / "maestro"
    return Path(project or os.getcwd()) / ".claude" / "conductor"


def version(hooks=None):
    """VERSION file next to the hooks, else the plugin manifest's version, else '?'."""
    hd = Path(hooks or hooks_dir())
    vf = hd / "VERSION"
    if vf.is_file():
        try:
            return vf.read_text(encoding="utf-8").strip() or "?"
        except OSError:
            return "?"
    try:
        v = json.loads(manifest_path(hd.parent).read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError, AttributeError):
        return "?"
    return v.strip() if isinstance(v, str) and v.strip() else "?"


def read_payload():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def project_dir(payload):
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd())


def project_name(payload):
    return project_dir(payload).name or "?"


def read_config(cdir):
    try:
        cfg = json.loads((cdir / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return cfg if isinstance(cfg, dict) else {}


def log_error(cdir, msg):
    if cdir is None:
        return
    try:
        cdir.mkdir(parents=True, exist_ok=True)
        log = cdir / "hooks.log"
        stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        try:
            old = log.read_text(encoding="utf-8").splitlines()
        except OSError:
            old = []
        line = " ".join(str(msg).split())[:500]
        old = [*old, f"{stamp} {line}"][-LOG_LIMIT:]
        log.write_text("\n".join(old) + "\n", encoding="utf-8")
    except Exception:  # noqa: BLE001, S110
        pass


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def ledger_lines(cdir):
    try:
        return (cdir / "ledger.jsonl").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None


def ledger_rows(lines):
    rows = []
    for line in lines or []:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def count_unrated(lines):
    return sum(1 for r in ledger_rows(lines) if r.get("outcome") == "unrated")


def read_state(cdir):
    try:
        data = json.loads((cdir / "state.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(cdir, state):
    cdir.mkdir(parents=True, exist_ok=True)
    tmp = cdir / "state.json.tmp"
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, cdir / "state.json")


def short_model(model_id):
    m = str(model_id or "").lower()
    for needle, name in (
        ("haiku", "haiku"),
        ("sonnet", "sonnet"),
        ("opus", "opus"),
        ("fable", "fable"),
        ("mythos", "fable"),
    ):
        if needle in m:
            return name
    return str(model_id or "?")


def _ts(value):
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def _num(usage, key):
    v = usage.get(key)
    return v if isinstance(v, int) and not isinstance(v, bool) else 0


def parse_lines(lines):
    """Usage summary from transcript lines (str), or None when there is no assistant line."""
    last_usage = {}  # message id -> usage of its LAST line, in first-seen order
    last_id = None
    model = None
    task = None
    first_ts = last_ts = None
    for n, line in enumerate(lines):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        t = _ts(d.get("timestamp")) if d.get("timestamp") else None
        if t is not None:
            first_ts = first_ts or t
            last_ts = t
        msg = d.get("message") if isinstance(d.get("message"), dict) else {}
        if d.get("type") == "user" and task is None and not d.get("isMeta"):
            text = " ".join(_text(msg.get("content")).split())
            if text:
                task = text[:80]
        if d.get("type") == "assistant" and isinstance(msg.get("usage"), dict):
            mid = msg.get("id") or f"_line{n}"
            last_usage[mid] = msg["usage"]
            last_id = mid
            if msg.get("model") and msg.get("model") != "<synthetic>":
                model = msg["model"]
    if last_id is None:
        return None
    sums = {k: sum(_num(u, k) for u in last_usage.values()) for k in FIELDS}
    final = sum(_num(last_usage[last_id], k) for k in FIELDS)
    duration = 0
    if first_ts and last_ts:
        try:
            duration = max(0, int((last_ts - first_ts).total_seconds() * 1000))
        except TypeError:  # naive vs aware timestamps
            duration = 0
    return {
        "model": short_model(model),
        "input_tokens": sums["input_tokens"],
        "output_tokens": sums["output_tokens"],
        "cache_write_tokens": sums["cache_creation_input_tokens"],
        "cache_read_tokens": sums["cache_read_input_tokens"],
        "final_context_tokens": final,
        "messages": len(last_usage),
        "duration_ms": duration,
        "task": task or "",
    }


def parse_transcript(path):
    """parse_lines of a file, retrying while it is missing or has no assistant line."""
    for attempt in range(RETRIES + 1):
        if attempt:
            time.sleep(RETRY_DELAY)
        try:
            lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, TypeError, ValueError):
            continue
        result = parse_lines(lines)
        if result is not None:
            return result
    return None


def run_hook(main):
    """Run main(payload, cdir); log and swallow every error."""
    cdir = None
    try:
        payload = read_payload()
        cdir = data_dir(project_dir(payload))
        main(payload, cdir)
    except Exception as e:  # noqa: BLE001
        log_error(cdir, f"{Path(sys.argv[0]).name}: {type(e).__name__}: {e}")
    return 0
