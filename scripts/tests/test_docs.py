"""Packaging and documentation checks."""

import json
import re

from helpers import REPO, SCRIPTS


def test_hooks_json_shape():
    data = json.loads((REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert list(data) == ["hooks"]
    assert set(data["hooks"]) == {"SessionStart", "SubagentStop", "Stop"}
    for event, entries in data["hooks"].items():
        assert len(entries) == 1, event
        for entry in entries:
            for h in entry["hooks"]:
                assert h["type"] == "command" and h["timeout"] == 10
                cmd = h["command"]
                assert "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/" in cmd
                names = re.findall(r"/scripts/hooks/(\w+\.py)", cmd)
                assert len(names) == 2 and names[0] == names[1]
                assert (SCRIPTS / "hooks" / names[0]).is_file()
                assert cmd.startswith("python3 ") and " || python " in cmd


def test_plugin_version_matches_changelog():
    plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    top = re.search(r"^## (\d+\.\d+\.\d+)", (REPO / "CHANGELOG.md").read_text(encoding="utf-8"), re.MULTILINE)
    assert top and plugin["version"] == top.group(1) == "2.3.0"
    assert plugin["name"] == "elashry-maestro"
    assert {"hooks", "ledger"} <= set(plugin["keywords"])
    assert "version: 2.3.0" in (REPO / "assets" / "badges" / "version.svg").read_text(encoding="utf-8")


def test_docs_mention_the_ledger():
    for name in ("PRIVACY.md", "README.md"):
        assert "ledger.jsonl" in (REPO / name).read_text(encoding="utf-8"), name
    assert "log_task_text" in (REPO / "PRIVACY.md").read_text(encoding="utf-8")


def test_skill_is_short_and_documents_hooks():
    text = (REPO / "skills" / "maestro" / "SKILL.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) < 200
    for needle in ("ledger.jsonl", "owner.md", "ledger.py rate", "export-store", "## 9."):
        assert needle in text, needle


def test_no_leftover_source_paths_in_scripts():
    for path in [SCRIPTS / "ledger.py", *(SCRIPTS / "hooks").glob("*.py")]:
        assert "fable-conductor is installed" not in path.read_text(encoding="utf-8"), path
        assert not path.read_text(encoding="utf-8").startswith("#!"), path
