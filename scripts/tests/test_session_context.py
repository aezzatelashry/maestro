"""SessionStart context: bundled agents line, first-message menu rule, size cap."""

import json

from helpers import hook, install_plugin


def plugin_with_menu(tmp_path, menu=True):
    root = tmp_path / "plugin"
    scripts = install_plugin(root)
    if menu:
        ref = root / "skills" / "maestro" / "references"
        ref.mkdir(parents=True)
        (ref / "menu.md").write_text("# menu\n", encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    return root, scripts, project


def context(scripts, project):
    r = hook("session_start", {}, project, scripts=scripts)
    assert r.returncode == 0
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def test_agents_line_names_all_four(tmp_path):
    _, scripts, project = plugin_with_menu(tmp_path, menu=False)
    ctx = context(scripts, project)
    assert "`elashry-maestro:runner` (Haiku, long commands)" in ctx
    assert "`elashry-maestro:builder` (Sonnet)" in ctx
    assert "`elashry-maestro:reviewer` (Sonnet, ordinary review)" in ctx
    assert "`elashry-maestro:deep-reviewer` (Opus, risky review)" in ctx


def test_menu_sentence_uses_absolute_path_when_file_exists(tmp_path):
    root, scripts, project = plugin_with_menu(tmp_path)
    ctx = context(scripts, project)
    menu = (root / "skills" / "maestro" / "references" / "menu.md").resolve()
    assert f"show the menu from {menu} as pick-an-option choices" in ctx
    assert "if it is a concrete task, do the task." in ctx
    assert "not a concrete task (a greeting, 'continue', something vague)" in ctx


def test_menu_sentence_omitted_without_file(tmp_path):
    _, scripts, project = plugin_with_menu(tmp_path, menu=False)
    ctx = context(scripts, project)
    assert "show the menu from" not in ctx and "concrete task" not in ctx


def test_size_cap_with_menu_and_long_owner(tmp_path):
    _, scripts, project = plugin_with_menu(tmp_path)
    data = project / "_home" / ".claude" / "maestro"
    data.mkdir(parents=True)
    (data / "owner.md").write_text("\n".join(f"- owner {i} " + "o" * 90 for i in range(200)) + "\n", encoding="utf-8")
    (data / "rules.md").write_text("R" * 4000, encoding="utf-8")
    (data / "lessons.md").write_text("\n".join(f"lesson {i} " + "z" * 100 for i in range(20)) + "\n", encoding="utf-8")
    (data / "ledger.jsonl").write_text(
        json.dumps({"outcome": "unrated", "agent_id": "a", "kind": "builder", "tokens": 1}) + "\n", encoding="utf-8"
    )
    ctx = context(scripts, project)
    assert len(ctx) <= 3000
    assert "elashry-maestro:deep-reviewer" in ctx and "show the menu from" in ctx
    assert "owner 199" in ctx and "owner 0 " not in ctx
    assert "Unrated dispatches: 1" in ctx  # the tail is never cut off
