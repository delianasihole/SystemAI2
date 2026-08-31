import datetime
import json
from pathlib import Path
from typing import Any, Dict

APPROVALS_PATH = "data/approvals.json"


def load_approvals(path: str = APPROVALS_PATH) -> Dict[str, Any]:
    """Return {email_id: {"status", "decided_by", "timestamp"}} decided so far."""
    p = Path(path)
    if not p.exists():
        return {}
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def save_approval(email_id: str, status: str, decided_by: str, path: str = APPROVALS_PATH) -> Dict[str, Any]:
    """Record an admin's approve/reject decision for one email, overwriting any prior decision."""
    if status not in ("approved", "rejected", "pending"):
        raise ValueError(f"invalid approval status: {status}")

    approvals = load_approvals(path)
    if status == "pending":
        approvals.pop(email_id, None)
    else:
        approvals[email_id] = {
            "status": status,
            "decided_by": decided_by,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(approvals, f, indent=2)

    return approvals.get(email_id)
