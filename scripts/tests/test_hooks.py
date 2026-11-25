import json

import hooklib
from helpers import (
    hook,
    install_project,
    ledger_rows_of,
    stop_payload,
    transcript,
    write_tx,
)


def test_parser_sums_and_final(tmp_path):
    r = hooklib.parse_transcript(write_tx(tmp_path / "t.jsonl", transcript()))
    assert r["input_tokens"] == 15
    assert r["output_tokens"] == 29
    assert r["cache_write_tokens"] == 100
    assert r["cache_read_tokens"] == 300
    assert r["final_context_tokens"] == 314
    assert r["messages"] == 2
    assert r["model"] == "sonnet"
    assert r["duration_ms"] == 62000
    assert r["task"] == "Build the thing " + "x" * 64
    assert len(r["task"]) == 80


def test_parser_model_mapping():
    for mid, short in [
        ("claude-haiku-4-5", "haiku"),
        ("claude-sonnet-5-5", "sonnet"),
        ("claude-opus-4-7", "opus"),
        ("claude-fable-1", "fable"),
        ("claude-mythos-x", "fable"),
        ("gpt-x", "gpt-x"),
    ]:
        lines = [json.dumps(x) for x in transcript(mid)]
        assert hooklib.parse_lines(lines)["model"] == short


def test_parser_no_assistant():
    assert hooklib.parse_lines(['{"type":"user"}', "garbage"]) is None


def test_subagent_stop_end_to_end(tmp_path):
    tx = write_tx(tmp_path / "t.jsonl", transcript())
    payload = stop_payload(tx)
    r = hook("subagent_stop", payload, tmp_path)
    assert r.returncode == 0
    msg = json.loads(r.stdout)["systemMessage"]
    assert "المايسترو" in msg
    assert "144" in msg  # 15 + 29 + 100 new work
    assert "300" in msg and "sonnet" in msg and "builder" in msg
    assert "hookSpecificOutput" not in r.stdout
    assert r.stdout.isascii()  # ensure_ascii JSON
    ledger = tmp_path / ".claude" / "conductor" / "ledger.jsonl"
    rows = ledger_rows_of(ledger)
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "hook" and row["outcome"] == "unrated"
    assert row["tokens"] == 144 and row["cache_read_tokens"] == 300
    assert row["agent_id"] == "a1" and row["final_context_tokens"] == 314
    assert row["role"] == row["kind"] == "builder" and row["messages"] == 2
    assert row["project"] == tmp_path.name
    r2 = hook("subagent_stop", payload, tmp_path)
    assert r2.returncode == 0 and r2.stdout == ""
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1


def test_subagent_stop_missing_transcript(tmp_path):
    payload = stop_payload(tmp_path / "nope.jsonl", agent_type="runner")
    r = hook("subagent_stop", payload, tmp_path)
    assert r.returncode == 0
    assert "تعذّر" in json.loads(r.stdout)["systemMessage"]
    assert not (tmp_path / ".claude" / "conductor" / "ledger.jsonl").exists()


def test_hooks_survive_garbage_stdin(tmp_path):
    for name in ("subagent_stop", "session_start", "stop_nudge", "statusline"):
        r = hook(name, None, tmp_path, raw="{not json")
        assert r.returncode == 0, name


def conductor_fixture(tmp_path, rows=2, unrated=1):
    c = install_project(tmp_path)
    (c / "hooks" / "VERSION").write_text("2.4.0\n", encoding="utf-8")
    lines = []
    for i in range(rows):
        outcome = "unrated" if i < unrated else "pass"
        lines.append(
            json.dumps(
                {
                    "ts": f"2026-11-24T10:00:0{i}+00:00",
                    "model": "sonnet",
                    "kind": "builder",
                    "tokens": 5,
                    "outcome": outcome,
                    "task": "t",
                    "agent_id": f"ag{i}",
                }
            )
        )
    (c / "ledger.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return c


def test_session_start_silent_without_version_in_project_layout(tmp_path):
    r = hook("session_start", {}, tmp_path)
    assert r.returncode == 0 and r.stdout == ""


def test_session_start_full(tmp_path):
    c = conductor_fixture(tmp_path)
    (c / "owner.md").write_text(
        "# owner\n- يحب الردود القصيرة\n- يسأل بخيارات\nnot a bullet\n",
        encoding="utf-8",
    )
    (c / "lessons.md").write_text("# L\n\nlesson one\nlesson two\n", encoding="utf-8")
    (c / "rules.md").write_text("# rules\nnever merge on Friday\n", encoding="utf-8")
    r = hook("session_start", {}, tmp_path)
    out = json.loads(r.stdout)
    assert "2.4.0" in out["systemMessage"]
    assert "المايسترو شغّال هنا" in out["systemMessage"]
    assert "بدون تقييم" in out["systemMessage"]
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "The Maestro plugin (elashry-maestro) is active" in ctx
    assert "menu" not in ctx
    assert "- يحب الردود القصيرة" in ctx and "- يسأل بخيارات" in ctx
    assert "not a bullet" not in ctx
    assert "Owner profile (follow without being reminded):" in ctx
    assert "User rules (take precedence over the skill defaults):\n# rules\nnever merge on Friday" in ctx
    assert "lesson two" in ctx and "Unrated dispatches: 1" in ctx
    cmd = f'python3 "{(c / "ledger.py").resolve()}"'
    assert f"{cmd} rate --agent-id ID" in ctx and f"{cmd} unrated" in ctx
    assert ".claude/conductor/ledger.py" not in ctx.replace(str(c.resolve()), "")
    assert len(ctx) <= 3000


def test_session_start_caps_long_inputs(tmp_path):
    c = conductor_fixture(tmp_path)
    (c / "owner.md").write_text(
        "\n".join(f"- line {i} " + "y" * 80 for i in range(100)) + "\n",
        encoding="utf-8",
    )
    (c / "rules.md").write_text("R" * 5000, encoding="utf-8")
    (c / "lessons.md").write_text(
        "\n".join(f"lesson {i} " + "z" * 150 for i in range(20)) + "\n",
        encoding="utf-8",
    )
    ctx = json.loads(hook("session_start", {}, tmp_path).stdout)["hookSpecificOutput"]["additionalContext"]
    assert len(ctx) <= 3000
    assert "line 99" in ctx and "line 0 " not in ctx
    assert "lesson 19" in ctx and "lesson 0 " not in ctx
    assert ctx.count("R") <= 800 + 20  # rules capped near 800 characters (the word "Rules" adds a few)
    assert "Unrated dispatches: 1" in ctx  # the tail part is never cut off


def test_stop_nudge_flow(tmp_path):
    c = conductor_fixture(tmp_path, rows=2, unrated=1)
    cmd = f'python3 "{(c / "ledger.py").resolve()}"'
    active = hook("stop_nudge", {"stop_hook_active": True}, tmp_path)
    assert active.stdout == ""
    r = hook("stop_nudge", {}, tmp_path)
    out = json.loads(r.stdout)
    assert out["decision"] == "block"
    assert f"{cmd} unrated" in out["reason"]
    assert f"{cmd} rate --agent-id ID --outcome" in out["reason"]
    assert out["reason"].startswith("Maestro housekeeping")
    assert "export-store" not in out["reason"]
    assert json.loads((c / "state.json").read_text())["nudged_lines"] == 2
    assert hook("stop_nudge", {}, tmp_path).stdout == ""
    with (c / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"outcome": "unrated", "agent_id": "z"}) + "\n")
    assert json.loads(hook("stop_nudge", {}, tmp_path).stdout)["decision"] == "block"


def test_stop_nudge_dashboard_and_config(tmp_path):
    c = conductor_fixture(tmp_path, rows=2, unrated=0)
    assert hook("stop_nudge", {}, tmp_path).stdout == ""  # nothing to do
    with (c / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"outcome": "pass"}) + "\n")
    (c / "dashboard.md").write_text("address", encoding="utf-8")
    out = json.loads(hook("stop_nudge", {}, tmp_path).stdout)
    assert "export-store" in out["reason"] and "unrated dispatches" not in out["reason"]
    assert str(c / "dashboard.md") in out["reason"]
    (c / "config.json").write_text('{"nudge": false}', encoding="utf-8")
    with (c / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"outcome": "unrated"}) + "\n")
    assert hook("stop_nudge", {}, tmp_path).stdout == ""


def test_statusline(tmp_path):
    full = {
        "model": {"display_name": "Sonnet 5.5"},
        "cost": {"total_cost_usd": 1.234},
        "workspace": {"project_dir": str(tmp_path)},
    }
    r = hook("statusline", full, tmp_path / "other")
    assert r.stdout.strip() == "Maestro ✓ | Sonnet 5.5 | $1.23"
    conductor_fixture(tmp_path, rows=3, unrated=2)
    r = hook("statusline", full, tmp_path / "other")
    assert r.stdout.strip() == "Maestro ✓ | Sonnet 5.5 | $1.23 | agents 3 (2 unrated)"
    nocost = {
        "model": {"display_name": "Haiku"},
        "workspace": {"project_dir": str(tmp_path)},
    }
    r = hook("statusline", nocost, tmp_path)
    assert r.stdout.strip() == "Maestro ✓ | Haiku | agents 3 (2 unrated)"
    assert hook("statusline", {}, tmp_path / "x").stdout.strip() == "Maestro ✓"


def test_error_goes_to_log_and_exits_zero(tmp_path):
    c = conductor_fixture(tmp_path)
    (c / "state.json").mkdir()  # unreadable as a file -> write_state fails
    (c / "ledger.jsonl").write_text('{"outcome":"unrated"}\n', encoding="utf-8")
    r = hook("stop_nudge", {}, tmp_path)
    assert r.returncode == 0 and r.stdout == ""
    assert (c / "hooks.log").read_text(encoding="utf-8").strip()


def test_hooks_log_is_capped(tmp_path):
    for i in range(250):
        hooklib.log_error(tmp_path, f"error {i}")
    lines = (tmp_path / "hooks.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 200 and lines[-1].endswith("error 249")


def test_log_task_text_false_blanks_task(tmp_path):
    c = install_project(tmp_path)
    (c / "config.json").write_text('{"log_task_text": false}', encoding="utf-8")
    tx = write_tx(tmp_path / "t.jsonl", transcript())
    assert hook("subagent_stop", stop_payload(tx), tmp_path).returncode == 0
    row = ledger_rows_of(c / "ledger.jsonl")[0]
    assert row["task"] == "" and row["tokens"] == 144
    assert "Build" not in (c / "ledger.jsonl").read_text(encoding="utf-8")


def test_log_task_text_default_keeps_80_chars(tmp_path):
    c = install_project(tmp_path)
    (c / "config.json").write_text('{"log_task_text": true}', encoding="utf-8")
    tx = write_tx(tmp_path / "t.jsonl", transcript())
    hook("subagent_stop", stop_payload(tx), tmp_path)
    assert len(ledger_rows_of(c / "ledger.jsonl")[0]["task"]) == 80
