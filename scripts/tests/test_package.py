import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    import importlib.util

    spec = importlib.util.spec_from_file_location("package_skill", REPO / "scripts" / "package_skill.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = tmp_path_factory.mktemp("zip") / "skill.zip"
    module.build(out, REPO)
    return out


def test_archive_layout(built):
    with zipfile.ZipFile(built) as zf:
        names = set(zf.namelist())
    top = "elashry-pro-maestro-skill/"
    assert {f"{top}SKILL.md", f"{top}LICENSE", f"{top}NOTICE", f"{top}references/routing.md"} <= names
    assert f"{top}references/documents.md" in names
    assert all(n.startswith(top) for n in names)
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
    # the plugin-only parts do not ship in the standalone skill
    assert not any(n.startswith(f"{top}agents/") or "/hooks/" in n for n in names)


def test_skill_is_renamed_only_in_the_frontmatter(built):
    with zipfile.ZipFile(built) as zf:
        text = zf.read("elashry-pro-maestro-skill/SKILL.md").decode("utf-8")
    source = (REPO / "skills" / "maestro" / "SKILL.md").read_text(encoding="utf-8")
    assert "name: elashry-pro-maestro-skill" in text.split("---")[1]
    assert "name: maestro" not in text.split("---")[1]
    assert len(text.splitlines()) == len(source.splitlines())


def test_archive_is_reproducible(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("package_skill", REPO / "scripts" / "package_skill.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    a, b = tmp_path / "a.zip", tmp_path / "b.zip"
    module.build(a, REPO)
    module.build(b, REPO)
    assert a.read_bytes() == b.read_bytes()
