"""Data directory rule, plugin layout, project field and the by-project report."""

import json

import hooklib
import ledger
from helpers import (
    LEDGER,
    SCRIPTS,
    hook,
    install_plugin,
    install_project,
    ledger_rows_of,
    run,
    stop_payload,
    transcript,
    write_tx,
)


def set_home(monkeypatch, home):
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


def test_data_dir_three_cases_and_both_agree(tmp_path, monkeypatch):
    plugin_scripts = install_plugin(tmp_path / "plugin")
    project_scripts = install_project(tmp_path / "proj")  # no plugin.json beside it
    home = tmp_path / "home"
    set_home(monkeypatch, home)
    monkeypatch.delenv("MAESTRO_HOME", raising=False)
    project = tmp_path / "proj"
    # (a) MAESTRO_HOME wins in either layout
    monkeypatch.setenv("MAESTRO_HOME", str(tmp_path / "mh"))
    for scripts in (plugin_scripts, project_scripts):
        assert hooklib.data_dir(project, scripts) == ledger.data_dir(project, scripts) == tmp_path / "mh"
    monkeypatch.delenv("MAESTRO_HOME")
    # (b) plugin layout -> ~/.claude/maestro
    expected = home / ".claude" / "maestro"
    assert hooklib.data_dir(project, plugin_scripts) == ledger.data_dir(project, plugin_scripts) == expected
    # (c) per-project layout -> <project>/.claude/conductor
    expected = project / ".claude" / "conductor"
    assert hooklib.data_dir(project, project_scripts) == ledger.data_dir(project, project_scripts) == expected


def test_data_dir_project_defaults_to_cwd_in_both(tmp_path, monkeypatch):
    project_scripts = install_project(tmp_path / "proj")
    monkeypatch.delenv("MAESTRO_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    a = hooklib.data_dir(None, project_scripts).resolve()
    b = ledger.data_dir(None, project_scripts).resolve()
    assert a == b == (tmp_path / ".claude" / "conductor").resolve()


def test_the_real_repo_is_a_plugin_layout():
    assert hooklib.is_plugin_layout() and ledger.is_plugin_layout()
    assert hooklib.scripts_dir() == SCRIPTS


def test_ledger_default_path_follows_the_rule(tmp_path, monkeypatch):
    plugin_scripts = install_plugin(tmp_path / "plugin")
    set_home(monkeypatch, tmp_path / "home")
    monkeypatch.delenv("MAESTRO_HOME", raising=False)
    monkeypatch.delenv("CONDUCTOR_LEDGER", raising=False)
    assert ledger.ledger_path(None) == tmp_path / "home" / ".claude" / "maestro" / "ledger.jsonl"
    monkeypatch.setenv("MAESTRO_HOME", str(tmp_path / "mh"))
    assert ledger.ledger_path(None) == tmp_path / "mh" / "ledger.jsonl"
    monkeypatch.setenv("CONDUCTOR_LEDGER", str(tmp_path / "x.jsonl"))
    assert ledger.ledger_path(None) == tmp_path / "x.jsonl"
    assert ledger.ledger_path(str(tmp_path / "y.jsonl")) == tmp_path / "y.jsonl"
    assert plugin_scripts.is_dir()


def test_plugin_layout_hooks_end_to_end(tmp_path):
    scripts = install_plugin(tmp_path / "plugin", version="7.8.9")
    project = tmp_path / "my-project"
    project.mkdir()
    home = project / "_home"
    tx = write_tx(tmp_path / "t.jsonl", transcript())
    # session start: no VERSION file, still runs, version from plugin.json
    r = hook("session_start", {}, project, scripts=scripts)
    out = json.loads(r.stdout)
    assert "7.8.9" in out["systemMessage"] and "المايسترو شغّال هنا" in out["systemMessage"]
    ctx = out["hookSpecificOutput"]["additionalContext"]
    cmd = f'python3 "{(scripts.resolve() / "ledger.py")}"'
    assert f"{cmd} rate --agent-id ID" in ctx
    # subagent stop: row goes to ~/.claude/maestro with the project folder name
    r = hook("subagent_stop", stop_payload(tx), project, scripts=scripts)
    assert r.returncode == 0 and "المايسترو" in json.loads(r.stdout)["systemMessage"]
    ledger_file = home / ".claude" / "maestro" / "ledger.jsonl"
    rows = ledger_rows_of(ledger_file)
    assert len(rows) == 1 and rows[0]["project"] == "my-project" and rows[0]["tokens"] == 144
    assert not (project / ".claude").exists()
    # stop nudge reads the same place and names the real ledger.py
    nudge = json.loads(hook("stop_nudge", {}, project, scripts=scripts).stdout)
    assert f"{cmd} unrated" in nudge["reason"]
    # ledger.py in the plugin tree defaults to the same file
    r = run(scripts / "ledger.py", "unrated", home=home)
    assert "a1" in r.stdout
    r = run(scripts / "ledger.py", "rate", "--agent-id", "a1", "--outcome", "pass", home=home)
    assert "1 row(s) changed" in r.stdout
    assert ledger_rows_of(ledger_file)[0]["outcome"] == "pass"
    rep = run(scripts / "ledger.py", "report", home=home).stdout
    assert str(ledger_file) in rep and "by project" in rep and "my-project" in rep
    # session start now shows the count
    out = json.loads(hook("session_start", {}, project, scripts=scripts).stdout)
    assert "1" in out["systemMessage"] and "بدون تقييم" not in out["systemMessage"]


def test_maestro_home_override_in_both_layouts(tmp_path):
    scripts = install_plugin(tmp_path / "plugin")
    tx = write_tx(tmp_path / "t.jsonl", transcript())
    mh = tmp_path / "elsewhere"
    (tmp_path / "p1").mkdir()
    hook("subagent_stop", stop_payload(tx), tmp_path / "p1", env_extra={"MAESTRO_HOME": mh}, scripts=scripts)
    assert len(ledger_rows_of(mh / "ledger.jsonl")) == 1
    (tmp_path / "p2").mkdir()
    hook("subagent_stop", stop_payload(tx, agent_id="b"), tmp_path / "p2", env_extra={"MAESTRO_HOME": mh})
    assert len(ledger_rows_of(mh / "ledger.jsonl")) == 2
    assert not (tmp_path / "p2" / ".claude" / "conductor" / "ledger.jsonl").exists()
    out = run(LEDGER, "unrated", env_extra={"MAESTRO_HOME": mh}, home=tmp_path / "h")
    assert out.stdout.count("\n") == 2


def test_banner_version_sources(tmp_path):
    scripts = install_plugin(tmp_path / "plugin", version="1.2.3")
    hooks = scripts / "hooks"
    assert hooklib.version(hooks) == "1.2.3"
    (hooks / "VERSION").write_text("4.5.6\n", encoding="utf-8")
    assert hooklib.version(hooks) == "4.5.6"  # VERSION file wins
    (hooks / "VERSION").unlink()
    (tmp_path / "plugin" / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
    assert hooklib.version(hooks) == "?"
    (tmp_path / "plugin" / ".claude-plugin" / "plugin.json").unlink()
    assert hooklib.version(hooks) == "?"
    assert hooklib.version() == json.loads((SCRIPTS.parent / ".claude-plugin" / "plugin.json").read_text())["version"]


def test_project_field_from_cwd_when_no_env(tmp_path):
    c = install_project(tmp_path / "proj")
    tx = write_tx(tmp_path / "t.jsonl", transcript())
    payload = {**stop_payload(tx), "cwd": str(tmp_path / "from-cwd")}
    r = hook("subagent_stop", payload, tmp_path / "proj", env_extra={"CLAUDE_PROJECT_DIR": None})
    assert r.returncode == 0, r.stderr
    # data dir is derived from the same project dir (the payload cwd), project field is its name
    rows = ledger_rows_of(tmp_path / "from-cwd" / ".claude" / "conductor" / "ledger.jsonl")
    assert rows[0]["project"] == "from-cwd"
    assert c.is_dir()


def row(project=None, outcome="pass", model="sonnet", **extra):
    r = {"ts": "2026-11-24T10:00:00+00:00", "model": model, "kind": "builder", "tokens": 10, "outcome": outcome}
    if project is not None:
        r["project"] = project
    return {**r, **extra}


def test_report_file_shows_by_project_when_rows_carry_project(tmp_path):
    f = tmp_path / "l.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in [row("alpha"), row("alpha"), row("beta", "fail")]) + "\n")
    out = run(LEDGER, "report", "--file", f).stdout
    assert "by project" in out and "alpha" in out and "beta" in out
    data = json.loads(run(LEDGER, "report", "--json", "--file", f).stdout)
    assert {p["project"]: p["dispatches"] for p in data["by_project"]} == {"alpha": 2, "beta": 1}


def test_report_file_without_project_is_unchanged(tmp_path):
    f = tmp_path / "l.jsonl"
    f.write_text(json.dumps(row()) + "\n")
    out = run(LEDGER, "report", "--file", f).stdout
    assert "by project" not in out
    assert "by_project" not in json.loads(run(LEDGER, "report", "--json", "--file", f).stdout)


def test_report_all_prefers_the_rows_own_project(tmp_path):
    lf = tmp_path / "dirname" / ".claude" / "conductor" / "ledger.jsonl"
    lf.parent.mkdir(parents=True)
    lf.write_text("\n".join(json.dumps(r) for r in [row("own-name"), row()]) + "\n")
    data = json.loads(run(LEDGER, "report", "--all", tmp_path, "--json").stdout)
    assert {p["project"] for p in data["by_project"]} == {"own-name", "dirname"}


def test_export_store_uses_the_rows_own_project(tmp_path):
    lf = tmp_path / "dirname" / ".claude" / "conductor" / "ledger.jsonl"
    lf.parent.mkdir(parents=True)
    lf.write_text("\n".join(json.dumps(r) for r in [row("own-name"), row()]) + "\n")
    out = json.loads(run(LEDGER, "export-store", "--file", lf).stdout)
    assert [w["data"]["project"] for w in out] == ["own-name", "dirname"]


def test_run_from_unrelated_cwd_does_not_touch_it(tmp_path):
    scripts = install_plugin(tmp_path / "plugin")
    other = tmp_path / "other"
    other.mkdir()
    r = run(scripts / "ledger.py", "unrated", cwd=other, home=tmp_path / "home")
    assert r.returncode == 0 and r.stdout == ""
    assert not (other / ".claude").exists()
