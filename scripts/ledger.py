"""Dispatch ledger for the Maestro plugin (ported from fable-conductor).

  ledger.py add --model sonnet --role builder --tokens 48211 \
      --duration-ms 93000 --outcome pass --task "users import endpoint" [--kind implement]
  ledger.py report [--last N] [--json] [--file F | --all DIR] [--prices FILE]

The ledger is `ledger.jsonl` in the data directory: env MAESTRO_HOME if set; else
~/.claude/maestro when this script sits in a plugin layout (<scripts dir>/../.claude-plugin/plugin.json
exists); else <project>/.claude/conductor, where <project> is the git root of the current
directory (or the current directory). Override the file with --file or CONDUCTOR_LEDGER.
It records subagent dispatches only; the Maestro's own token use is not visible to this
script. --prices FILE (JSON) adds a cost estimate to the report: a model's value is either
a number (blended dollars per million over `tokens`) or an object with any of input, output,
cache_write, cache_read (dollars per million, applied to the matching category fields of a
row; rows without them are "unpriced").

Row fields. Always: ts, model, role, kind, tokens, duration_ms, outcome, task.
Optional: project (folder name, set by the hooks), agent_id, source ("hook" | "manual"), input_tokens, output_tokens,
cache_write_tokens, cache_read_tokens, final_context_tokens, messages.
outcome is pass | rework | escalated | fail, or "unrated" (logged by a hook, not
judged yet; `rate` changes it, `report` leaves it out of pass rates and flags).

`tokens` in a manual row (copied from a completion notice) is only the size of the
subagent's FINAL request, not the work of the whole run. In a hook row `tokens` =
input + output + cache_write (new work; cache reads excluded) and cache_read is kept
separately in cache_read_tokens.

  ledger.py rate (--agent-id ID | --last N) --outcome pass|rework|escalated|fail
  ledger.py unrated
  ledger.py export-store [--all]   JSON batches for the shared dashboard store
"""

import argparse
import datetime as dt
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

OUTCOMES = ("pass", "rework", "escalated", "fail")
UNRATED = "unrated"
ADD_OUTCOMES = (*OUTCOMES, UNRATED)
SOURCES = ("hook", "manual")
NUM_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_write_tokens",
    "cache_read_tokens",
    "final_context_tokens",
    "messages",
)
PRICE_KEYS = ("input", "output", "cache_write", "cache_read")
CATEGORY = (
    ("input_tokens", "input"),
    ("output_tokens", "output"),
    ("cache_write_tokens", "cache_write"),
    ("cache_read_tokens", "cache_read"),
)
BATCH = 50
TIERS = ("haiku", "sonnet", "opus", "fable")
MIN_SAMPLE = 4  # dispatches before a rate means anything
REWORK_LIMIT = 0.30  # above this, route up or fix the brief
SMALL_TOKENS = 25_000  # an Opus dispatch this small that passed first time may be over-routed


def project_root():
    """Git root of the current directory, or the current directory."""
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        root = os.getcwd()
    return Path(root)


def is_plugin_layout(scripts=None):
    """True when scripts/ sits next to .claude-plugin/plugin.json (installed as the plugin)."""
    return (Path(scripts or Path(__file__).resolve().parent).parent / ".claude-plugin" / "plugin.json").is_file()


def data_dir(project=None, scripts=None):
    """Where learning files live: MAESTRO_HOME, else ~/.claude/maestro (plugin), else <project>/.claude/conductor."""
    env = os.environ.get("MAESTRO_HOME")
    if env:
        return Path(env).expanduser()
    if is_plugin_layout(scripts):
        return Path.home() / ".claude" / "maestro"
    return Path(project or project_root()) / ".claude" / "conductor"


def ledger_path(arg):
    if arg:
        return Path(arg)
    if os.environ.get("CONDUCTOR_LEDGER"):
        return Path(os.environ["CONDUCTOR_LEDGER"])
    return data_dir() / "ledger.jsonl"


def cmd_add(a):
    path = ledger_path(a.file)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "model": a.model.lower(),
        "role": a.role.lower(),
        "kind": (a.kind or a.role).lower(),
        "tokens": a.tokens,
        "duration_ms": a.duration_ms,
        "outcome": a.outcome,
        "task": a.task,
    }
    if a.agent_id:
        row["agent_id"] = a.agent_id
    if a.source:
        row["source"] = a.source
    for name in NUM_FIELDS:
        v = getattr(a, name)
        if v is not None:
            row[name] = v
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"logged: {row['model']}/{row['role']} {row['outcome']} {row['tokens']} tok -> {path}")


def load(path, last):
    if not path.exists():
        return [], 0
    rows, bad = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            bad += 1
    return (rows[-last:] if last else rows), bad


def summarise(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[(r.get("model", "?"), r.get("kind") or r.get("role", "?"))].append(r)
    out = []
    for (model, kind), rs in sorted(groups.items()):
        n = len(rs)
        counts = {o: sum(1 for r in rs if r.get("outcome") == o) for o in OUTCOMES}
        tokens = sum(int(r.get("tokens") or 0) for r in rs)
        out.append(
            {
                "model": model,
                "kind": kind,
                "n": n,
                **counts,
                "tokens": tokens,
                "avg_tokens": tokens // n,
                "first_pass_rate": round(counts["pass"] / n, 2),
            }
        )
    return out


def flags(summary):
    notes = []
    for s in summary:
        if s["n"] < MIN_SAMPLE:
            continue
        label = f"{s['model']} on '{s['kind']}'"
        not_first = 1 - s["first_pass_rate"]
        if not_first > REWORK_LIMIT:
            notes.append(
                f"UNDER-ROUTED or weak briefs: {label} passed first time only "
                f"{s['pass']}/{s['n']}. Route this kind up a tier, or fix its brief template."
            )
        if s["model"] == "opus" and s["first_pass_rate"] == 1 and s["avg_tokens"] < SMALL_TOKENS:
            notes.append(
                f"POSSIBLY OVER-ROUTED: {label} passed {s['n']}/{s['n']} first time at "
                f"~{s['avg_tokens']} tokens each. Try Sonnet for this kind and compare."
            )
        if (
            s["model"] == "sonnet"
            and s["first_pass_rate"] == 1
            and s["kind"] in ("runner", "scout", "search", "extract", "summarise", "summarize")
        ):
            notes.append(f"POSSIBLY OVER-ROUTED: {label} is mechanical work passing every time. Try Haiku.")
    return notes


def load_all(base, last):
    """Rows from every ledger in base and its immediate subdirectories."""
    base = Path(base)
    candidates = [base] + sorted(d for d in base.iterdir() if d.is_dir())
    rows, bad, found = [], 0, 0
    for d in candidates:
        f = d / ".claude" / "conductor" / "ledger.jsonl"
        if not f.is_file():
            continue
        found += 1
        got, b = load(f, 0)
        bad += b
        name = d.resolve().name
        for r in got:
            r.setdefault("project", name)
        rows.extend(got)
    return (rows[-last:] if last else rows), bad, found


def by_project(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r.get("project", "?")].append(r)
    return [
        {
            "project": name,
            "dispatches": len(rs),
            "tokens": sum(int(r.get("tokens") or 0) for r in rs),
            "first_pass": sum(1 for r in rs if r.get("outcome") == "pass"),
        }
        for name, rs in sorted(groups.items())
    ]


def load_prices(path):
    """Model -> number (blended $/M) or {category: $/M} from a JSON file; ValueError if unusable."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as e:
        raise ValueError(f"cannot read prices file {path}: {e.strerror or e}") from e
    except ValueError as e:
        raise ValueError(f"prices file {path} is not valid JSON: {e}") from e
    items = data.items() if isinstance(data, dict) else None
    if items is None:
        raise ValueError(f"prices file {path} must be a JSON object of model: dollars per million tokens")

    def good(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0

    prices = {}
    for key, value in items:
        if key.startswith("_"):
            continue
        if isinstance(value, dict):
            bad = [k for k, v in value.items() if k not in PRICE_KEYS or not good(v)]
            if bad or not value:
                raise ValueError(
                    f"price for '{key}' in {path} must be a number or an object of "
                    f"{'/'.join(PRICE_KEYS)} non-negative numbers, got {value!r}"
                )
        elif not good(value):
            raise ValueError(f"price for '{key}' in {path} must be a non-negative number, got {value!r}")
        prices[key.lower()] = value
    return prices


def row_cost(row, price):
    """Dollars for a row under an object price, or None if the row lacks the category fields."""
    if any(not isinstance(row.get(f), (int, float)) for f, _ in CATEGORY):
        return None
    return sum(row[f] * price.get(k, 0) for f, k in CATEGORY) / 1_000_000


def cmd_report(a):
    prices = None
    if a.prices:
        try:
            prices = load_prices(a.prices)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
    projects = None
    if a.all:
        base = Path(a.all)
        if not base.is_dir():
            print(f"not a directory: {base}", file=sys.stderr)
            return 2
        path = base
        rows, bad, found = load_all(base, a.last)
        if not found:
            print(f"no ledgers found under {base}")
            return 0
        projects = by_project(rows)
    else:
        path = ledger_path(a.file)
        rows, bad = load(path, a.last)
        if any(isinstance(r, dict) and "project" in r for r in rows):
            projects = by_project(rows)
    if not rows:
        print(f"no dispatches recorded at {path}")
        return
    rated = [r for r in rows if r.get("outcome") != UNRATED]
    n_unrated = len(rows) - len(rated)
    summary = summarise(rated)
    notes = flags(summary)
    by_tier = defaultdict(lambda: {"n": 0, "tokens": 0})
    for r in rows:
        t = by_tier[r.get("model", "?")]
        t["n"] += 1
        t["tokens"] += int(r.get("tokens") or 0)
    total_tokens = sum(t["tokens"] for t in by_tier.values())
    passed = sum(1 for r in rated if r.get("outcome") == "pass")
    unpriced_rows = 0
    if prices is not None:
        unpriced = sorted(m for m in by_tier if m not in prices)
        total_cost = 0.0
        for m, t in by_tier.items():
            price = prices.get(m, 0)
            if isinstance(price, dict):
                raw = 0.0
                for r in rows:
                    if r.get("model", "?") != m:
                        continue
                    c = row_cost(r, price)
                    if c is None:
                        unpriced_rows += 1
                    else:
                        raw += c
            else:
                raw = t["tokens"] * price / 1_000_000
            total_cost += raw
            t["cost"] = round(raw, 4)

    if a.json:
        out = {
            "ledger": str(path),
            "dispatches": len(rows),
            "unreadable_lines": bad,
            "total_tokens": total_tokens,
            "first_pass_rate": round(passed / len(rated), 2) if rated else 0.0,
            "by_tier": by_tier,
            "by_kind": summary,
            "flags": notes,
            "rows": rows[-50:],
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        }
        if n_unrated:
            out["unrated"] = n_unrated
        if projects is not None:
            out["by_project"] = projects
        if prices is not None:
            out["estimated_cost"] = round(total_cost, 4)
            out["unpriced_models"] = unpriced
            if unpriced_rows:
                out["unpriced_rows"] = unpriced_rows
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print(f"ledger: {path}")
    print(f"dispatches: {len(rows)}   subagent tokens: {total_tokens:,}   first-time pass: {passed}/{len(rated)}")
    if n_unrated:
        print(f"unrated: {n_unrated}")
    if prices is not None:
        print(f"estimated cost: ${total_cost:.2f}")
        if unpriced:
            print(f"unpriced: {', '.join(unpriced)}")
        if unpriced_rows:
            print(f"unpriced rows: {unpriced_rows}")
    if bad:
        print(f"warning: {bad} unreadable line(s) skipped")
    if projects is not None:
        print("\nby project")
        print(f"  {'project':<20} {'dispatches':>10} {'tokens':>10} {'first-time pass':>16}")
        for p in projects:
            print(
                f"  {p['project']:<20} {p['dispatches']:>10} {p['tokens']:>10,} {p['first_pass']:>9}/{p['dispatches']}"
            )
    print("\nby tier")
    order = {t: i for i, t in enumerate(TIERS)}
    for tier, t in sorted(by_tier.items(), key=lambda kv: order.get(kv[0], 99)):
        share = (100 * t["tokens"] // total_tokens) if total_tokens else 0
        print(f"  {tier:<8} {t['n']:>3} dispatches  {t['tokens']:>10,} tokens  {share:>3}%")
    print("\nby tier and kind")
    print(f"  {'model':<8} {'kind':<14} {'n':>3} {'pass':>4} {'rework':>6} {'escal':>5} {'fail':>4} {'avg tok':>9}")
    for s in summary:
        print(
            f"  {s['model']:<8} {s['kind']:<14} {s['n']:>3} {s['pass']:>4} {s['rework']:>6} "
            f"{s['escalated']:>5} {s['fail']:>4} {s['avg_tokens']:>9,}"
        )
    print("\nflags")
    if notes:
        for n in notes:
            print(f"  - {n}")
    else:
        print(f"  none (rates are only judged from {MIN_SAMPLE} dispatches of a kind upward)")


def parse_line(raw):
    """Row dict from one ledger line (bytes or str), or None if blank/unreadable."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if not raw.strip():
        return None
    try:
        row = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return row if isinstance(row, dict) else None


def write_atomic(path, data):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def cmd_rate(a):
    path = ledger_path(a.file)
    if not path.is_file():
        print(f"no ledger at {path}: nothing matched")
        return 0
    lines = path.read_bytes().split(b"\n")
    parsed = [(i, parse_line(raw)) for i, raw in enumerate(lines)]
    parsed = [(i, r) for i, r in parsed if r is not None]
    if a.agent_id:
        targets = [(i, r) for i, r in parsed if r.get("agent_id") == a.agent_id]
    else:
        targets = parsed[-a.last :] if a.last > 0 else []
    if not targets:
        print("nothing matched: no row changed")
        return 0
    changed = 0
    for i, r in targets:
        who = f"line {i + 1} ({r.get('model', '?')}/{r.get('kind', '?')}, {r.get('agent_id') or 'no agent id'})"
        if r.get("outcome") != UNRATED:
            print(f"already rated {r.get('outcome')}, left alone: {who}")
            continue
        r["outcome"] = a.outcome
        cr = b"\r" if lines[i].endswith(b"\r") else b""
        lines[i] = json.dumps(r, ensure_ascii=False).encode("utf-8") + cr
        changed += 1
        print(f"rated {a.outcome}: {who}")
    if changed:
        write_atomic(path, b"\n".join(lines))
    print(f"{changed} row(s) changed")
    return 0


def cmd_unrated(a):
    path = ledger_path(a.file)
    if not path.is_file():
        return 0
    for n, raw in enumerate(path.read_bytes().split(b"\n"), 1):
        r = parse_line(raw)
        if r is None or r.get("outcome") != UNRATED:
            continue
        print(
            f"{n}  {r.get('ts', '?')}  {r.get('model', '?')}  {r.get('kind', '?')}  "
            f"{r.get('agent_id') or '-'}  {r.get('task', '')}"
        )
    return 0


def read_state(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def doc_id(ts, n):
    digits = re.sub(r"\D", "", str(ts))[:14].ljust(14, "0")
    return f"{digits[:8]}T{digits[8:]}-{n:03d}"


def cmd_export_store(a):
    path = ledger_path(a.file)
    if not path.is_file():
        print(f"no ledger at {path}", file=sys.stderr)
        return 0
    state_path = path.parent / "state.json"
    state = read_state(state_path)
    synced = state.get("synced_lines", 0)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if a.all or not isinstance(synced, int) or not 0 <= synced <= len(lines):
        synced = 0
    fallback_project = path.resolve().parent.parent.parent.name
    writes = []
    for n, raw in enumerate(lines, 1):
        if n <= synced:
            continue
        r = parse_line(raw)
        if r is None:
            continue
        data = {"ts": r.get("ts", ""), "project": r.get("project") or fallback_project}
        for k in ("model", "role", "kind", "tokens", "duration_ms", "outcome", "task"):
            data[k] = r.get(k, 0 if k in ("tokens", "duration_ms") else "")
        for k in ("agent_id", "source", *NUM_FIELDS):
            if k in r:
                data[k] = r[k]
        writes.append(
            {
                "op": "set",
                "collection": "data/conductor/dispatches",
                "doc_id": doc_id(r.get("ts", ""), n),
                "data": data,
            }
        )
    for i in range(0, len(writes), BATCH):
        print(json.dumps(writes[i : i + BATCH], ensure_ascii=False))
    state["synced_lines"] = len(lines)
    write_atomic(state_path, (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode())
    print(f"exported {len(writes)} row(s)", file=sys.stderr)
    return 0


def main():
    p = argparse.ArgumentParser(description="Maestro dispatch ledger")
    sub = p.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="record one dispatch")
    add.add_argument("--model", required=True, help="haiku | sonnet | opus | fable")
    add.add_argument("--role", required=True, help="scout | runner | builder | reviewer | ...")
    add.add_argument("--kind", help="kind of work, for grouping (defaults to the role)")
    add.add_argument("--tokens", type=int, default=0)
    add.add_argument("--duration-ms", type=int, default=0)
    add.add_argument("--outcome", required=True, choices=ADD_OUTCOMES)
    add.add_argument("--task", required=True, help="a few words naming the piece")
    add.add_argument("--agent-id")
    add.add_argument("--source", choices=SOURCES, help="hook | manual (manual if absent)")
    for name in NUM_FIELDS:
        add.add_argument("--" + name.replace("_", "-"), type=int)
    add.add_argument("--file")
    add.set_defaults(func=cmd_add)

    rep = sub.add_parser("report", help="summarise the ledger and print routing flags")
    rep.add_argument("--last", type=int, default=0, help="only the last N dispatches")
    rep.add_argument("--json", action="store_true")
    rep.add_argument(
        "--prices",
        metavar="FILE",
        help="JSON of model: dollars per million tokens, for a blended cost",
    )
    grp = rep.add_mutually_exclusive_group()
    grp.add_argument("--file")
    grp.add_argument(
        "--all",
        metavar="DIR",
        help="combine every project ledger in DIR and its immediate subdirectories",
    )
    rep.set_defaults(func=cmd_report)

    rate = sub.add_parser("rate", help="judge unrated rows")
    who = rate.add_mutually_exclusive_group(required=True)
    who.add_argument("--agent-id")
    who.add_argument("--last", type=int, help="the last N rows")
    rate.add_argument("--outcome", required=True, choices=OUTCOMES)
    rate.add_argument("--file")
    rate.set_defaults(func=cmd_rate)

    un = sub.add_parser("unrated", help="list unrated rows")
    un.add_argument("--file")
    un.set_defaults(func=cmd_unrated)

    ex = sub.add_parser("export-store", help="print JSON batches of rows for the store")
    ex.add_argument("--all", action="store_true", help="ignore the sync marker")
    ex.add_argument("--file")
    ex.set_defaults(func=cmd_export_store)

    a = p.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
