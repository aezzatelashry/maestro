import json

from helpers import LEDGER, run


def add(ledger_file, tokens=100, outcome="pass"):
    r = run(
        LEDGER,
        "add",
        "--model",
        "sonnet",
        "--role",
        "builder",
        "--tokens",
        tokens,
        "--outcome",
        outcome,
        "--task",
        "t",
        "--file",
        ledger_file,
    )
    assert r.returncode == 0, r.stderr


def test_report_json_has_rows_and_generated_at(tmp_path):
    f = tmp_path / "l.jsonl"
    add(f)
    data = json.loads(run(LEDGER, "report", "--json", "--file", f).stdout)
    assert len(data["rows"]) == 1
    assert "generated_at" in data


def test_report_all_aggregates(tmp_path):
    for name, n in (("alpha", 1), ("beta", 2)):
        for _ in range(n):
            add(tmp_path / name / ".claude" / "conductor" / "ledger.jsonl")
    data = json.loads(run(LEDGER, "report", "--all", tmp_path, "--json").stdout)
    assert data["dispatches"] == 3
    assert {p["project"] for p in data["by_project"]} == {"alpha", "beta"}
    assert "by project" in run(LEDGER, "report", "--all", tmp_path).stdout


def test_report_all_none(tmp_path):
    r = run(LEDGER, "report", "--all", tmp_path)
    assert r.returncode == 0
    assert f"no ledgers found under {tmp_path}" in r.stdout


def test_all_and_file_exclusive(tmp_path):
    r = run(LEDGER, "report", "--all", tmp_path, "--file", tmp_path / "x")
    assert r.returncode != 0


def add_model(ledger_file, model, tokens):
    r = run(
        LEDGER,
        "add",
        "--model",
        model,
        "--role",
        "builder",
        "--tokens",
        tokens,
        "--outcome",
        "pass",
        "--task",
        "t",
        "--file",
        ledger_file,
    )
    assert r.returncode == 0, r.stderr


def priced_ledger(tmp_path):
    f = tmp_path / "l.jsonl"
    add_model(f, "haiku", 1_500_000)
    add_model(f, "sonnet", 123_456)
    add_model(f, "zeta", 1000)
    add_model(f, "alpha", 5)
    return f


def write_prices(directory, text):
    p = directory / "prices.json"
    p.write_text(text, encoding="utf-8")
    return p


def test_prices_json_cost_and_unpriced(tmp_path):
    f = priced_ledger(tmp_path)
    p = write_prices(tmp_path, '{"Haiku": 1.0, "sonnet": 3.33}')
    r = run(LEDGER, "report", "--json", "--file", f, "--prices", p)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    # haiku 1.5; sonnet 123456 * 3.33 / 1e6 = 0.41110848 -> 0.4111
    assert data["by_tier"]["haiku"]["cost"] == 1.5
    assert data["by_tier"]["sonnet"]["cost"] == 0.4111
    assert data["by_tier"]["zeta"]["cost"] == 0
    assert data["by_tier"]["alpha"]["cost"] == 0
    assert data["unpriced_models"] == ["alpha", "zeta"]
    assert data["estimated_cost"] == 1.9111


def test_prices_total_sums_unrounded_costs(tmp_path):
    f = tmp_path / "l.jsonl"
    add_model(f, "haiku", 1)
    add_model(f, "sonnet", 1)
    p = write_prices(tmp_path, '{"haiku": 30000, "sonnet": 30000}')
    data = json.loads(run(LEDGER, "report", "--json", "--file", f, "--prices", p).stdout)
    assert data["by_tier"]["haiku"]["cost"] == 0.03
    assert data["estimated_cost"] == 0.06
    assert data["unpriced_models"] == []


def test_prices_text_lines(tmp_path):
    f = priced_ledger(tmp_path)
    p = write_prices(tmp_path, '{"haiku": 1.0, "sonnet": 3.33}')
    lines = run(LEDGER, "report", "--file", f, "--prices", p).stdout.splitlines()
    i = next(n for n, line in enumerate(lines) if line.startswith("dispatches:"))
    assert lines[i + 1] == "estimated cost: $1.91"
    assert lines[i + 2] == "unpriced: alpha, zeta"
    full = write_prices(tmp_path, '{"haiku": 1, "sonnet": 1, "zeta": 1, "alpha": 1}')
    out = run(LEDGER, "report", "--file", f, "--prices", full).stdout
    assert "estimated cost: $" in out
    assert "unpriced" not in out


def test_report_without_prices_is_unchanged(tmp_path):
    f = priced_ledger(tmp_path)
    out = run(LEDGER, "report", "--file", f).stdout
    assert "estimated cost" not in out
    assert "unpriced" not in out
    data = json.loads(run(LEDGER, "report", "--json", "--file", f).stdout)
    assert "estimated_cost" not in data
    assert "unpriced_models" not in data
    assert all("cost" not in t for t in data["by_tier"].values())


def test_bad_prices_exit_2(tmp_path):
    f = priced_ledger(tmp_path)
    cases = [
        tmp_path / "nope.json",
        write_prices(tmp_path, "{not json"),
        write_prices(tmp_path, "[1, 2]"),
        write_prices(tmp_path, '{"haiku": "1.0"}'),
        write_prices(tmp_path, '{"haiku": true}'),
        write_prices(tmp_path, '{"haiku": -1}'),
        write_prices(tmp_path, '{"haiku": NaN}'),
        write_prices(tmp_path, '{"haiku": Infinity}'),
    ]
    for p in cases:
        r = run(LEDGER, "report", "--file", f, "--prices", p)
        assert r.returncode == 2, p
        assert r.stderr.strip(), p
        assert r.stdout == ""


def test_bad_prices_exit_2_even_without_ledger(tmp_path):
    r = run(
        LEDGER,
        "report",
        "--file",
        tmp_path / "none.jsonl",
        "--prices",
        tmp_path / "nope.json",
    )
    assert r.returncode == 2
    assert "nope.json" in r.stderr


def test_prices_underscore_keys_ignored(tmp_path):
    f = priced_ledger(tmp_path)
    p = write_prices(tmp_path, '{"_note": "made up", "_n": 3, "haiku": 1.0}')
    r = run(LEDGER, "report", "--json", "--file", f, "--prices", p)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["unpriced_models"] == ["alpha", "sonnet", "zeta"]


def test_prices_with_all(tmp_path):
    add_model(tmp_path / "a" / ".claude" / "conductor" / "ledger.jsonl", "haiku", 500_000)
    add_model(tmp_path / "b" / ".claude" / "conductor" / "ledger.jsonl", "haiku", 500_000)
    p = write_prices(tmp_path / "a", '{"haiku": 2}')
    data = json.loads(run(LEDGER, "report", "--all", tmp_path, "--json", "--prices", p).stdout)
    assert data["estimated_cost"] == 2.0
    assert data["by_tier"]["haiku"]["cost"] == 2.0
    assert "by_project" in data
    out = run(LEDGER, "report", "--all", tmp_path, "--prices", p).stdout
    assert "estimated cost: $2.00" in out.splitlines()
    assert "by project" in out


def test_prices_with_empty_ledger_reports_no_dispatches(tmp_path):
    p = write_prices(tmp_path, '{"haiku": 1}')
    r = run(LEDGER, "report", "--file", tmp_path / "none.jsonl", "--prices", p)
    assert r.returncode == 0
    assert "no dispatches recorded" in r.stdout
    assert "estimated cost" not in r.stdout


# ---- unrated rows, rate, export-store, category prices ----


def raw_row(n, outcome="unrated", model="sonnet", **extra):
    row = {
        "ts": f"2026-11-24T10:00:{n:02d}+00:00",
        "model": model,
        "role": "builder",
        "kind": "builder",
        "tokens": 100,
        "duration_ms": 5,
        "outcome": outcome,
        "task": f"task {n}",
        "agent_id": f"ag{n}",
        **extra,
    }
    return json.dumps(row, ensure_ascii=False)


def write_ledger(tmp_path, lines):
    f = tmp_path / "p" / ".claude" / "conductor" / "ledger.jsonl"
    f.parent.mkdir(parents=True)
    f.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return f


def test_add_new_fields(tmp_path):
    f = tmp_path / "l.jsonl"
    r = run(
        LEDGER, "add", "--model", "opus", "--role", "builder", "--outcome", "unrated",
        "--task", "t", "--agent-id", "x9", "--source", "hook",
        "--input-tokens", 1, "--output-tokens", 2, "--cache-write-tokens", 3,
        "--cache-read-tokens", 4, "--final-context-tokens", 5, "--messages", 6,
        "--file", f,
    )  # fmt: skip
    assert r.returncode == 0, r.stderr
    row = json.loads(f.read_text(encoding="utf-8"))
    assert row["agent_id"] == "x9" and row["source"] == "hook" and row["messages"] == 6
    assert row["cache_read_tokens"] == 4 and row["outcome"] == "unrated"


def test_rate_changes_only_unrated_and_preserves_bytes(tmp_path):
    lines = [
        raw_row(1, "pass"),
        "not json at all",
        raw_row(2),
        "",
        raw_row(3),
        raw_row(4, "fail"),
    ]
    f = write_ledger(tmp_path, lines)
    before = f.read_bytes().split(b"\n")
    r = run(LEDGER, "rate", "--agent-id", "ag2", "--outcome", "rework", "--file", f)
    assert r.returncode == 0 and "1 row(s) changed" in r.stdout
    after = f.read_bytes().split(b"\n")
    assert [i for i in range(len(before)) if before[i] != after[i]] == [2]
    assert json.loads(after[2])["outcome"] == "rework"
    r = run(LEDGER, "rate", "--agent-id", "ag2", "--outcome", "pass", "--file", f)
    assert "already rated" in r.stdout and "0 row(s) changed" in r.stdout
    assert json.loads(f.read_bytes().split(b"\n")[2])["outcome"] == "rework"
    r = run(LEDGER, "rate", "--last", 3, "--outcome", "escalated", "--file", f)
    assert "1 row(s) changed" in r.stdout and "already rated" in r.stdout
    assert json.loads(f.read_bytes().split(b"\n")[4])["outcome"] == "escalated"
    r = run(LEDGER, "rate", "--agent-id", "nobody", "--outcome", "pass", "--file", f)
    assert r.returncode == 0 and "nothing matched" in r.stdout


def test_unrated_listing(tmp_path):
    f = write_ledger(tmp_path, [raw_row(1, "pass"), raw_row(2), raw_row(3)])
    before = f.read_bytes()
    r = run(LEDGER, "unrated", "--file", f)
    out = r.stdout.splitlines()
    assert len(out) == 2 and out[0].startswith("2 ") and "ag2" in out[0]
    assert "task 3" in out[1] and f.read_bytes() == before


def test_export_store_batches_and_marker(tmp_path):
    f = write_ledger(tmp_path, [raw_row(i % 60, source="hook") for i in range(120)])
    r = run(LEDGER, "export-store", "--file", f)
    batches = [json.loads(x) for x in r.stdout.splitlines()]
    assert [len(b) for b in batches] == [50, 50, 20]
    first = batches[0][0]
    assert first["op"] == "set" and first["collection"] == "data/conductor/dispatches"
    assert first["doc_id"] == "20261124T100000-001"
    assert first["data"]["project"] == "p" and first["data"]["source"] == "hook"
    assert "exported 120" in r.stderr
    state = f.parent / "state.json"
    assert json.loads(state.read_text())["synced_lines"] == 120
    assert run(LEDGER, "export-store", "--file", f).stdout == ""
    with f.open("a", encoding="utf-8") as fh:
        fh.write(raw_row(7) + "\n")
    state.write_text(json.dumps({"synced_lines": 120, "other": 1}))
    out = json.loads(run(LEDGER, "export-store", "--file", f).stdout)
    assert len(out) == 1 and out[0]["doc_id"].endswith("-121")
    assert json.loads(state.read_text()) == {"synced_lines": 121, "other": 1}
    r = run(LEDGER, "export-store", "--all", "--file", f)
    assert [len(json.loads(x)) for x in r.stdout.splitlines()] == [50, 50, 21]


def test_report_with_unrated(tmp_path):
    f = write_ledger(tmp_path, [raw_row(1, "pass"), raw_row(2, "fail"), raw_row(3)])
    r = run(LEDGER, "report", "--file", f)
    assert "unrated: 1" in r.stdout and "first-time pass: 1/2" in r.stdout
    assert r.stdout.index("dispatches: 3") < r.stdout.index("unrated: 1")
    j = json.loads(run(LEDGER, "report", "--json", "--file", f).stdout)
    assert j["unrated"] == 1 and j["first_pass_rate"] == 0.5 and j["dispatches"] == 3
    assert j["total_tokens"] == 300
    g = write_ledger(tmp_path / "x", [raw_row(1, "pass")])
    assert "unrated:" not in run(LEDGER, "report", "--file", g).stdout
    assert "unrated" not in json.loads(run(LEDGER, "report", "--json", "--file", g).stdout)


def test_prices_object_and_numeric(tmp_path):
    cat = {
        "input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "cache_write_tokens": 1_000_000,
        "cache_read_tokens": 1_000_000,
    }
    f = write_ledger(
        tmp_path,
        [
            raw_row(1, "pass", model="opus", **cat),
            raw_row(2, "pass", model="opus"),
            raw_row(3, "pass", model="haiku", tokens=2_000_000),
        ],
    )
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps(
            {
                "opus": {"input": 1, "output": 2, "cache_write": 3, "cache_read": 0.5},
                "haiku": 1.5,
            }
        )
    )
    j = json.loads(run(LEDGER, "report", "--json", "--prices", prices, "--file", f).stdout)
    assert j["unpriced_rows"] == 1
    assert j["by_tier"]["opus"]["cost"] == 6.5
    assert j["by_tier"]["haiku"]["cost"] == 3.0 + 0 and j["estimated_cost"] == 9.5
    t = run(LEDGER, "report", "--prices", prices, "--file", f).stdout
    assert "unpriced rows: 1" in t and "estimated cost: $9.50" in t
    prices.write_text('{"opus": {"bogus": 1}}')
    assert run(LEDGER, "report", "--prices", prices, "--file", f).returncode == 2
    plain = tmp_path / "plain.json"
    plain.write_text('{"haiku": 1.5, "opus": 5}')
    j = json.loads(run(LEDGER, "report", "--json", "--prices", plain, "--file", f).stdout)
    assert "unpriced_rows" not in j and j["by_tier"]["haiku"]["cost"] == 3.0
