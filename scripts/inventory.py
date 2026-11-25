"""Inventory of the skills, plugins and hooks installed for Claude Code on this machine.

  inventory.py [--json] [--home DIR]

Read-only. It lists every plugin with its skill count, the size of its skill
descriptions (which are loaded into every session) and the hook events it
registers, then the skill names that appear in more than one place. It never
disables, edits or deletes anything: deciding what to keep is the user's call.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DESCRIPTION = re.compile(r"^description:\s*(.*?)(?=^[A-Za-z][\w-]*:|^---)", re.DOTALL | re.MULTILINE)
NAME = re.compile(r"^name:\s*(.+)$", re.MULTILINE)


def read_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def safe_glob(folder, pattern):
    try:
        return sorted(folder.rglob(pattern))
    except OSError:
        return []


def safe_dirs(folder):
    try:
        return sorted(p for p in folder.iterdir() if p.is_dir())
    except OSError:
        return []


def plugin_name(folder):
    for candidate in (
        folder / "plugin.json",
        folder / ".claude-plugin" / "plugin.json",
    ):
        name = read_json(candidate).get("name")
        if isinstance(name, str) and name:
            return name
    meta = read_json(folder.with_name(folder.name + ".meta.json"))
    for key in ("name", "plugin_name"):
        if isinstance(meta.get(key), str) and meta[key]:
            return meta[key]
    return folder.name


def skills_in(folder):
    found = []
    for skill in safe_glob(folder, "SKILL.md"):
        try:
            text = skill.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        head = text.split("\n---", 1)[0] + "\n---"
        desc = DESCRIPTION.search(head)
        name = NAME.search(head)
        found.append(
            {
                "name": name.group(1).strip().strip("\"'") if name else skill.parent.name,
                "desc_chars": len(" ".join(desc.group(1).split())) if desc else 0,
            }
        )
    return found


def hook_events(folder):
    events = set()
    for hooks in safe_glob(folder, "hooks.json"):
        data = read_json(hooks).get("hooks", {})
        if isinstance(data, dict):
            events.update(event for event, value in data.items() if value)
    return sorted(events)


def collect(home):
    sources = []
    synced = home / "plugins" / "synced"
    if synced.is_dir():
        for bucket in safe_dirs(synced):
            for folder in safe_dirs(bucket):
                sources.append(("plugin", plugin_name(folder), folder))
    skills_root = home / "skills"
    if skills_root.is_dir():
        for folder in safe_dirs(skills_root):
            kind = "profile skills" if folder.name == "synced" else "personal skill"
            sources.append((kind, folder.name, folder))
    rows = []
    for kind, name, folder in sources:
        skills = skills_in(folder)
        events = hook_events(folder)
        if not skills and not events:
            continue
        rows.append(
            {
                "kind": kind,
                "name": name,
                "skills": len(skills),
                "desc_chars": sum(s["desc_chars"] for s in skills),
                "hooks": events,
                "skill_names": sorted(s["name"] for s in skills),
            }
        )
    return sorted(rows, key=lambda r: (-r["desc_chars"], r["name"]))


def duplicates(rows):
    seen = defaultdict(set)
    for row in rows:
        for skill in row["skill_names"]:
            seen[skill.lower()].add(row["name"])
    return {skill: sorted(owners) for skill, owners in sorted(seen.items()) if len(owners) > 1}


def main(argv=None):
    parser = argparse.ArgumentParser(description="inventory of installed skills, plugins and hooks")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--home", default=str(Path.home() / ".claude"), help="Claude config directory")
    args = parser.parse_args(argv)

    rows = collect(Path(args.home))
    dupes = duplicates(rows)
    starters = [r["name"] for r in rows if "SessionStart" in r["hooks"]]
    totals = {
        "sources": len(rows),
        "skills": sum(r["skills"] for r in rows),
        "desc_chars": sum(r["desc_chars"] for r in rows),
        "session_start_hooks": len(starters),
    }
    if args.json:
        print(
            json.dumps(
                {"totals": totals, "sources": rows, "duplicates": dupes},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"{'source':<34} {'kind':<15} {'skills':>6} {'desc chars':>10}  hooks")
    for r in rows:
        print(f"{r['name'][:33]:<34} {r['kind']:<15} {r['skills']:>6} {r['desc_chars']:>10}  {', '.join(r['hooks'])}")
    print(f"{'TOTAL':<34} {'':<15} {totals['skills']:>6} {totals['desc_chars']:>10}")
    print(f"\nrun at every session start ({len(starters)}): {', '.join(starters) or 'none'}")
    print(f"\nskill names found in more than one source ({len(dupes)})")
    for skill, owners in dupes.items():
        print(f"  {skill}: {', '.join(owners)}")
    print("\nThe totals are what is on disk. How much of it the app loads into each session is not visible from here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
