"""Run the capture from a Kenyan machine and publish the board to the `data` branch.

    python -m capture.publish

GitHub's runners sit outside Kenya, and at least one operator (SportyBet) answers them
with a refusal it does not give a Kenyan address. So a Kenyan machine can run this on a
schedule; it pushes only the small board files (board.json, status.json, quarantine.json)
as a single orphan commit to the `data` branch, force-replacing the previous one, so the
repository's history never grows. The deploy workflow prefers that board over its own
when it is fresher than 90 minutes and priced by more operators.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .common import DATA, REPO
from .run import main as capture_main

REMOTE = "https://github.com/GaeskaT/hundred-bob-finder.git"
FILES = ("board.json", "status.json", "quarantine.json")


def sh(*args, cwd=None):
    return subprocess.run(list(args), cwd=cwd, check=True, capture_output=True, text=True).stdout


def main() -> int:
    rc = capture_main()
    missing = [f for f in FILES if not (DATA / f).exists()]
    if missing:
        print("nothing to publish, missing:", missing)
        return 1
    work = Path(tempfile.mkdtemp(prefix="hbf-data-"))
    try:
        sh("git", "init", "-q", "-b", "data", cwd=work)
        for f in FILES:
            shutil.copy(DATA / f, work / f)
        (work / "README.md").write_text(
            "Latest board captured from a Kenyan machine by `python -m capture.publish`.\n"
            "Single orphan commit, force-replaced on every publish; the deploy workflow reads it.\n",
            encoding="utf-8")
        sh("git", "add", "-A", cwd=work)
        sh("git", "-c", "user.name=hundred-bob-capture", "-c", "user.email=capture@users.noreply.github.com",
           "commit", "-q", "-m", "board captured from Kenya", cwd=work)
        sh("git", "push", "-q", "--force", REMOTE, "data:data", cwd=work)
        print("published data branch:", ", ".join(FILES))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
