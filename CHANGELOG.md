# Changelog

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
