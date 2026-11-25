"""Shared test helpers: install copies of the scripts in each layout and run them as subprocesses."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
REPO = SCRIPTS.parent
LEDGER = str(SCRIPTS / "ledger.py")
IGNORE = shutil.ignore_patterns("__pycache__", "tests", "*.pyc")


def env_for(home, extra=None):
    """A clean environment: no Maestro variables, HOME inside the test directory."""
    env = {k: v for k, v in os.environ.items() if k not in ("MAESTRO_HOME", "CONDUCTOR_LEDGER", "CLAUDE_PROJECT_DIR")}
    env["HOME"] = env["USERPROFILE"] = str(home)
    for k, v in (extra or {}).items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = str(v)
    return env


def install_project(project):
    """Per-project layout: <project>/.claude/conductor/{ledger.py,hooks/}. Returns the conductor dir."""
    c = Path(project) / ".claude" / "conductor"
    if not c.exists():
        c.mkdir(parents=True)
        shutil.copytree(SCRIPTS / "hooks", c / "hooks", ignore=IGNORE)
        shutil.copy(SCRIPTS / "ledger.py", c / "ledger.py")
    return c


def install_plugin(root, version="9.9.9"):
    """Plugin layout: <root>/.claude-plugin/plugin.json and <root>/scripts/. Returns the scripts dir."""
    root = Path(root)
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "elashry-maestro", "version": version}), encoding="utf-8"
    )
    scripts = root / "scripts"
    if not scripts.exists():
        scripts.mkdir()
        shutil.copytree(SCRIPTS / "hooks", scripts / "hooks", ignore=IGNORE)
        shutil.copy(SCRIPTS / "ledger.py", scripts / "ledger.py")
    return scripts


def hook(name, payload, project, env_extra=None, raw=None, scripts=None):
    """Run a hook. Default: the per-project copy under <project>/.claude/conductor (installed on demand)."""
    project = Path(project)
    if scripts is None:
        hooks = install_project(project) / "hooks"
    else:
        hooks = Path(scripts) / "hooks"
    env = env_for(project / "_home", {"CLAUDE_PROJECT_DIR": project, **(env_extra or {})})
    return subprocess.run(
        [sys.executable, str(hooks / f"{name}.py")],
        input=raw if raw is not None else json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def run(script, *args, cwd=None, home=None, env_extra=None):
    home = home or Path(cwd or ".").resolve() / "_home"
    return subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
        env=env_for(home, env_extra),
    )


def asst(mid, model, i, o, cw, cr, ts):
    return {
        "type": "assistant",
        "timestamp": ts,
        "message": {
            "id": mid,
            "model": model,
            "usage": {
                "input_tokens": i,
                "output_tokens": o,
                "cache_creation_input_tokens": cw,
                "cache_read_input_tokens": cr,
            },
        },
    }


def transcript(model="claude-sonnet-5-5"):
    return [
        {
            "type": "user",
            "isMeta": True,
            "timestamp": "2026-11-24T10:00:00.000Z",
            "message": {"content": "<meta>"},
        },
        {
            "type": "user",
            "timestamp": "2026-11-24T10:00:01.000Z",
            "message": {"content": [{"type": "text", "text": "  Build   the\nthing " + "x" * 100}]},
        },
        asst("m1", model, 10, 1, 100, 0, "2026-11-24T10:00:02.000Z"),
        asst("m1", model, 10, 20, 100, 0, "2026-11-24T10:00:03.000Z"),
        {"type": "user", "message": {"content": "tool result"}},
        asst("m2", model, 5, 7, 0, 300, "2026-11-24T10:01:01.000Z"),
        asst("m2", model, 5, 9, 0, 300, "2026-11-24T10:01:02.000Z"),
    ]


def write_tx(path, lines):
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return path


def stop_payload(tx, agent_id="a1", agent_type="builder"):
    return {
        "hook_event_name": "SubagentStop",
        "agent_id": agent_id,
        "agent_type": agent_type,
        "agent_transcript_path": str(tx),
    }


def ledger_rows_of(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
