"""inventory.py on a fake config tree: counts, duplicates, --json, read-only, robustness."""

import json
import sys

from helpers import SCRIPTS, run

sys.path.insert(0, str(SCRIPTS))
import inventory

INVENTORY = SCRIPTS / "inventory.py"


def skill(folder, name, desc):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\nbody\n", encoding="utf-8")


def fake_home(tmp_path):
    home = tmp_path / "claude"
    a = home / "plugins" / "synced" / "mkt" / "alpha"
    b = home / "plugins" / "synced" / "mkt" / "beta"
    (a / ".claude-plugin").mkdir(parents=True)
    (a / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "alpha"}), encoding="utf-8")
    skill(a / "skills" / "review", "review", "12345 67890")
    skill(a / "skills" / "plan", "plan", "x" * 20)
    (a / "hooks").mkdir()
    (a / "hooks" / "hooks.json").write_text(
        json.dumps({"hooks": {"SessionStart": [{"hooks": []}], "Stop": []}}), encoding="utf-8"
    )
    (b / ".claude-plugin").mkdir(parents=True)
    (b / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "beta"}), encoding="utf-8")
    skill(b / "skills" / "review", "Review", "y" * 10)
    skill(home / "skills" / "mine" / "s", "mine", "z" * 5)
    return home


def snapshot(root):
    return sorted((str(p.relative_to(root)), p.read_bytes() if p.is_file() else None) for p in root.rglob("*"))


def test_json_shape_counts_and_duplicates(tmp_path):
    home = fake_home(tmp_path)
    before = snapshot(home)
    r = run(INVENTORY, "--json", "--home", home, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert set(data) == {"totals", "sources", "duplicates"}
    by = {s["name"]: s for s in data["sources"]}
    assert set(by) == {"alpha", "beta", "mine"}
    assert by["alpha"]["skills"] == 2 and by["alpha"]["desc_chars"] == 11 + 20
    assert by["alpha"]["hooks"] == ["SessionStart"]  # Stop has no entries
    assert by["beta"]["hooks"] == [] and by["mine"]["kind"] == "personal skill"
    assert data["totals"] == {"sources": 3, "skills": 4, "desc_chars": 11 + 20 + 10 + 5, "session_start_hooks": 1}
    assert data["duplicates"] == {"review": ["alpha", "beta"]}
    assert data["sources"][0]["name"] == "alpha"  # largest descriptions first
    assert snapshot(home) == before  # read-only


def test_text_output_ends_with_the_disclaimer(tmp_path):
    home = fake_home(tmp_path)
    out = run(INVENTORY, "--home", home, cwd=tmp_path).stdout
    assert "run at every session start (1): alpha" in out
    assert "skill names found in more than one source (1)" in out and "review: alpha, beta" in out
    last = out.strip().splitlines()[-1]
    assert "on disk" in last and "not visible from here" in last


def test_missing_home_and_odd_files(tmp_path):
    r = run(INVENTORY, "--json", "--home", tmp_path / "nothing", cwd=tmp_path)
    assert json.loads(r.stdout)["totals"]["sources"] == 0
    home = fake_home(tmp_path)
    odd = home / "plugins" / "synced" / "mkt" / "alpha"
    (odd / "hooks" / "hooks.json").write_text("{not json", encoding="utf-8")
    (odd / "plugin.json").write_text("[1, 2]", encoding="utf-8")
    (odd / "skills" / "bin").mkdir()
    (odd / "skills" / "bin" / "SKILL.md").write_bytes(b"\xff\xfe\x00 not utf8")
    (odd / "skills" / "dirlike" / "SKILL.md").mkdir(parents=True)  # a directory named SKILL.md
    (home / "plugins" / "synced" / "stray.txt").write_text("x", encoding="utf-8")
    r = run(INVENTORY, "--json", "--home", home, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    by = {s["name"]: s for s in json.loads(r.stdout)["sources"]}
    assert by["alpha"]["hooks"] == [] and by["alpha"]["skills"] >= 2


def test_collect_directly(tmp_path):
    rows = inventory.collect(fake_home(tmp_path))
    assert [r["name"] for r in rows] == ["alpha", "beta", "mine"]
