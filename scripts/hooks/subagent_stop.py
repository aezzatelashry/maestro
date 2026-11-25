"""SubagentStop hook: append one unrated ledger row from the subagent's transcript."""

import datetime as dt
import json
import sys

import hooklib as h


def fmt_duration(ms):
    secs = round(ms / 1000)
    if secs < 60:
        return f"{h.ltr(secs)} ث"
    minutes = f"{secs / 60:.1f}"
    return f"{h.ltr(minutes)} د"


def main(payload, cdir):
    agent_type = payload.get("agent_type") or "agent"
    agent_id = payload.get("agent_id")
    if agent_id and any(r.get("agent_id") == agent_id for r in h.ledger_rows(h.ledger_lines(cdir))):
        return
    u = h.parse_transcript(payload.get("agent_transcript_path"))
    if u is None:
        h.emit({"systemMessage": f"المايسترو · وكيل خلّص ({agent_type}) · تعذّر قراءة الاستخدام"})
        return
    new = u["input_tokens"] + u["output_tokens"] + u["cache_write_tokens"]
    task = u["task"] if h.read_config(cdir).get("log_task_text") is not False else ""
    row = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "project": h.project_name(payload),
        "model": u["model"],
        "role": agent_type,
        "kind": agent_type,
        "tokens": new,
        "duration_ms": u["duration_ms"],
        "outcome": "unrated",
        "task": task,
    }
    if agent_id:
        row["agent_id"] = agent_id
    row["source"] = "hook"
    for k in (
        "input_tokens",
        "output_tokens",
        "cache_write_tokens",
        "cache_read_tokens",
        "final_context_tokens",
        "messages",
    ):
        row[k] = u[k]
    cdir.mkdir(parents=True, exist_ok=True)
    with (cdir / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    new_s = h.ltr(f"{new:,}")
    read_s = h.ltr(f"{u['cache_read_tokens']:,}")
    h.emit(
        {
            "systemMessage": f"المايسترو · {u['model']} · {agent_type} · شغل جديد {new_s}"
            f" · قراءة كاش {read_s} · {fmt_duration(u['duration_ms'])}"
        }
    )


if __name__ == "__main__":
    sys.exit(h.run_hook(main))
