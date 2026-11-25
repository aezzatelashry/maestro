import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
for p in (str(HERE), str(SCRIPTS), str(SCRIPTS / "hooks")):
    if p not in sys.path:
        sys.path.insert(0, p)
