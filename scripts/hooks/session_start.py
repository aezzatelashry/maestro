"""SessionStart hook: show that Maestro is on and brief the model."""

import sys

import hooklib as h

LIMIT = 3000
RULES_CAP, OWNER_CAP, LESSONS_CAP = 800, 1200, 500
RULES_HEAD = "User rules (take precedence over the skill defaults):"
OWNER_HEAD = "Owner profile (follow without being reminded):"
LESSONS_HEAD = "Lessons from past runs:"


def intro():
    return (
        "The Maestro plugin (elashry-maestro) is active. For any request with two or more "
        "substantial pieces of work use its `maestro` skill on your own. Subagent runs are "
        "logged automatically by a hook: do not log them by hand; rate them with "
        f"`{h.ledger_cmd()} rate --agent-id ID --outcome pass|rework|escalated|fail` once you "
        "have judged them."
    )


def read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def newest_within(lines, cap):
    kept, size = [], 0
    for line in reversed(lines):
        if size + len(line) + 1 > cap:
            break
        kept.append(line)
        size += len(line) + 1
    return list(reversed(kept))


def main(payload, cdir):
    if not h.is_plugin_layout() and not (h.hooks_dir() / "VERSION").is_file():
        return
    lines = h.ledger_lines(cdir) or []
    total = len(h.ledger_rows(lines))
    unrated = h.count_unrated(lines)
    msg = f"المايسترو شغّال هنا · الإصدار {h.ltr(h.version())} · {h.ltr(total)} تكليف مسجّل"
    if unrated:
        msg += f", {h.ltr(unrated)} بدون تقييم"

    fixed = [intro()]
    if unrated:
        fixed.append(f"Unrated dispatches: {unrated} (run `{h.ledger_cmd()} unrated`)")
    used = len("\n\n".join(fixed))

    rules = read(cdir / "rules.md").strip()
    owner = [x.rstrip() for x in read(cdir / "owner.md").splitlines() if x.startswith("- ")]
    lessons = [x.strip() for x in read(cdir / "lessons.md").splitlines() if x.strip()][-5:]

    def room(head, cap):
        return min(cap, LIMIT - used - len(head) - 3)

    blocks = {}
    for key, head, cap in (
        ("rules", RULES_HEAD, RULES_CAP),
        ("owner", OWNER_HEAD, OWNER_CAP),
        ("lessons", LESSONS_HEAD, LESSONS_CAP),
    ):
        budget = room(head, cap)
        if budget <= 0:
            continue
        if key == "rules":
            body = rules[:budget].rstrip()
        else:
            body = "\n".join(newest_within(owner if key == "owner" else lessons, budget))
        if body:
            blocks[key] = f"{head}\n{body}"
            used += len(blocks[key]) + 2

    parts = [fixed[0], *(blocks[k] for k in ("rules", "owner", "lessons") if k in blocks), *fixed[1:]]
    context = "\n\n".join(parts)[:LIMIT]
    h.emit(
        {
            "systemMessage": msg,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            },
        }
    )


if __name__ == "__main__":
    sys.exit(h.run_hook(main))
