"""Build the standalone skill archive: elashry-pro-maestro-skill.zip.

  python3 scripts/package_skill.py [OUT_FILE]

The archive holds one folder, `elashry-pro-maestro-skill/`, with everything in
`skills/maestro/` plus LICENSE and NOTICE. In its SKILL.md the frontmatter name
`maestro` becomes `elashry-pro-maestro-skill`, so it does not clash with other
skills called maestro. The standalone form has no hooks and no bundled agents:
those belong to the plugin.
"""

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "elashry-pro-maestro-skill"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)  # so the same source always gives the same bytes


def _skip(path):
    return "__pycache__" in path.parts or path.suffix == ".pyc"


def build(out, root=ROOT):
    root = Path(root)
    skill_dir = root / "skills" / "maestro"
    files = sorted(p for p in skill_dir.rglob("*") if p.is_file() and not _skip(p))
    extra = [root / "LICENSE", root / "NOTICE"]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in extra:
            _add(zf, f"{NAME}/{path.name}", path.read_bytes())
        for path in files:
            rel = path.relative_to(skill_dir).as_posix()
            data = path.read_bytes()
            if rel == "SKILL.md":
                text = data.decode("utf-8")
                text, n = re.subn(r"^name: maestro\s*$", f"name: {NAME}", text, count=1, flags=re.MULTILINE)
                if n != 1:
                    raise SystemExit("SKILL.md has no 'name: maestro' line to rename")
                data = text.encode("utf-8")
            _add(zf, f"{NAME}/{rel}", data)
    return Path(out)


def _add(zf, arcname, data):
    info = zipfile.ZipInfo(arcname, date_time=FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out = Path(argv[0]) if argv else Path(f"{NAME}.zip")
    build(out)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
