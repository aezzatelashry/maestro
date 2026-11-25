# Changelog

## 2.3.0 (2026-11-25)

- **Hooks and an automatic ledger.** Three hooks (session start, subagent stop, stop) run local Python scripts, so usage is logged from real transcripts instead of relying on the model to remember. Each subagent run adds one `unrated` row to `~/.claude/maestro/ledger.jsonl`; the Maestro only rates the rows. The scripts are in `scripts/`, the hook list in `hooks/hooks.json`.
- **What a completion notice's token figure is.** It is only the size of the agent's last request, not its work. Matched exactly against five real transcripts, the real work was several times larger. Hook rows count input + output + cache writes as `tokens` and keep cache reads separately.
- **`ledger.py`:** `rate`, `unrated`, `export-store`, and `report --prices` with per-category prices (input, output, cache write, cache read). Rows now carry the project folder name, and `report` shows a by-project table when they do.
- **Opt-in status line:** `scripts/hooks/statusline.py`. A plugin cannot ship a status line, so it is added by hand (see the README).
- **Data directory rule:** `MAESTRO_HOME` if set; else `~/.claude/maestro` when the scripts sit in the plugin; else `<project>/.claude/conductor`. `config.json` there accepts `{"nudge": false}` and `{"log_task_text": false}`.
- **New privacy surface:** scripts that run on your machine, read agent transcripts and write `~/.claude/maestro/ledger.jsonl`, in every project. Nothing is sent anywhere. See PRIVACY.md.
- The standalone skill form has no hooks.
- **Not verified:** how the desktop and web apps display hook messages; the status line outside the terminal; Windows; installing these hooks through a cloud plugin install; `export-store` against a real dashboard store.

## 2.2.3 (2026-11-24)

- New README banner: gold Maestro name beside the baton mark.

## 2.2.2 (2026-11-24)

- Badges are now SVG files in `assets/badges/`, so they show even when shields.io is slow.

## 2.2.1 (2026-11-24)

- README: English banner in the icon's style, badges for license, version and Claude Code, and a diagram of how Maestro routes and reviews work.

## 2.2.0 (2026-11-24)

- The standalone skill is renamed **Elashry Pro Maestro-skill** (`elashry-pro-maestro-skill`) so it does not clash with other skills named maestro. Run it with `/elashry-pro-maestro-skill`.
- Release asset renamed to `elashry-pro-maestro-skill.zip`, with one-line download commands in the README.
- The plugin keeps its name, `elashry-maestro`, and its command, `/elashry-maestro:maestro`.

## 2.1.0 (2026-11-24)

- Can also be installed as a standalone skill in `~/.claude/skills/maestro`, run with `/maestro`.
- `maestro-skill.zip` attached to each release, with LICENSE and NOTICE inside.
- Template paths in the skill work in both plugin and standalone installs.

## 2.0.2 (2026-11-24)

- Privacy policy added (PRIVACY.md): the plugin collects and sends no data.

## 2.0.1 (2026-11-24)

- Support and documentation links added to the plugin manifest.

## 2.0.0 (2026-11-24)

- Plugin renamed from `maestro` to `elashry-maestro`, because the directory reserves "maestro" for an existing listing.
- Install with `/plugin install elashry-maestro@maestro`. The command is now `/elashry-maestro:maestro`.
- If you installed 1.x, run `/plugin uninstall maestro@maestro` first. Your files in `~/.claude/maestro/` are kept.

## 1.0.3 (2026-11-24)

- Plugin icon added: a conductor's baton sweeping an arc through three notes.

## 1.0.2 (2026-11-24)

- Author's name in Arabic added to the README and NOTICE.

## 1.0.1 (2026-11-24)

- License changed from MIT to Apache License 2.0, with a NOTICE file naming the author.
- Copyright line added at the top of each skill file.
- README laid out side by side: English and Arabic in two columns.

## 1.0.0 (2026-11-23)

First public release.

- Request sizing (small, medium, large or sensitive) that decides which steps run.
- Task plan with model, files, skills and evidence for each task.
- Model routing table, tuned over time from a run log.
- Executor brief in seven fixed parts.
- Review by the planning model, plus an independent fresh-context reviewer for large or sensitive work.
- Pre-mortem before dispatching large work.
- Run limits: parallel executors, attempts per model, model escalations and plan growth.
- Session state in `docs/STATUS.md`.
- Document mode for tenders, submittals, reports, decks and BOQs.
- Evidence table for each kind of task.
- Learning files kept in `~/.claude/maestro/`, outside the plugin folder.
