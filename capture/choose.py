"""Pick the board to deploy: the cloud capture in data/, or the Kenyan one in kenya/.

    python -m capture.choose kenya/board.json

The Kenyan board wins when it is fresher than 90 minutes and priced by more operators
than the cloud one; otherwise the cloud board stands. Either way status.json records
which was deployed and why, so the page can say so.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .common import DATA

FRESH = timedelta(minutes=90)


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def main(kenya_board: str) -> int:
    cloud = load(DATA / "board.json")
    kenya = load(Path(kenya_board))
    now = datetime.now(timezone.utc)
    choice, why = "cloud", "no Kenyan board"
    if kenya:
        age = now - datetime.fromisoformat(kenya["captured_at"])
        k_ops, c_ops = len(kenya.get("operators") or []), len((cloud or {}).get("operators") or [])
        if age <= FRESH and (cloud is None or k_ops > c_ops):
            choice, why = "kenya", f"Kenyan board {int(age.total_seconds() // 60)} min old with {k_ops} operators against {c_ops} from the cloud"
        else:
            why = f"Kenyan board {int(age.total_seconds() // 60)} min old with {k_ops} operators; cloud has {c_ops}"
    if choice == "kenya":
        DATA.mkdir(parents=True, exist_ok=True)
        for f in ("board.json", "status.json", "quarantine.json"):
            src = Path(kenya_board).parent / f
            if src.exists():
                shutil.copy(src, DATA / f)
        # the cloud CSV and raw archive do not match the Kenyan board; drop them rather than mislead
        for p in [DATA / "observations.csv"]:
            if p.exists():
                p.unlink()
        raw = DATA / "raw"
        if raw.exists():
            shutil.rmtree(raw)
    st = load(DATA / "status.json") or {}
    st["deployed_from"] = choice
    st["deploy_reason"] = why
    (DATA / "status.json").write_text(json.dumps(st, indent=2), encoding="utf-8")
    b = load(DATA / "board.json")
    if b is not None:
        b["deployed_from"] = choice
        (DATA / "board.json").write_text(json.dumps(b, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"deploying the {choice} board: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "kenya/board.json"))
