"""The bundled agents/*.md files: frontmatter keys and pinned values."""

from helpers import REPO

ALLOWED = {"name", "description", "model", "effort", "tools"}
MODELS = {"haiku", "sonnet", "opus"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
EXPECTED = {
    "runner": ("haiku", "low", "Bash, Read, Grep, Glob"),
    "builder": ("sonnet", "medium", None),
    "reviewer": ("sonnet", "medium", "Read, Grep, Glob, Bash"),
    "deep-reviewer": ("opus", "high", "Read, Grep, Glob, Bash"),
}


def frontmatter(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", path
    end = lines.index("---", 1)
    fields = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        assert sep and key == key.strip() and key, f"{path}: bad line {line!r}"
        assert key not in fields, f"{path}: duplicate key {key}"
        fields[key] = value.strip()
    return fields


def agent_files():
    return sorted((REPO / "agents").glob("*.md"))


def test_exactly_the_expected_agents():
    assert {p.stem for p in agent_files()} == set(EXPECTED)


def test_frontmatter_is_valid():
    for path in agent_files():
        fm = frontmatter(path)
        assert set(fm) <= ALLOWED, path
        assert {"name", "description", "model", "effort"} <= set(fm), path
        assert fm["name"] == path.stem
        assert fm["model"] in MODELS and fm["effort"] in EFFORTS
        assert fm["description"].strip(), path


def test_pinned_values():
    for name, (model, effort, tools) in EXPECTED.items():
        fm = frontmatter(REPO / "agents" / f"{name}.md")
        assert fm["model"] == model and fm["effort"] == effort, name
        assert fm.get("tools") == tools, name


def test_bodies_have_a_report_format():
    for path in agent_files():
        body = path.read_text(encoding="utf-8")
        assert "Report only this" in body, path
        assert "conductor" not in body.lower(), path
