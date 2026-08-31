import datetime
import json
from typing import Dict, Any, List


def log_event(
    audit_log: List[Dict[str, Any]],
    event: str,
    email_id: str,
    details: Dict[str, Any],
    reason: str = "",
) -> List[Dict[str, Any]]:
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "event": event,
        "email_id": email_id,
        "details": details,
        "reason": reason,
    }
    audit_log.append(entry)
    return audit_log


def write_audit_log(results, path: str = "audit.log") -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in results:
            for entry in r.audit_log:
                f.write(json.dumps(entry, default=str) + "\n")


def append_event(
    event: str,
    email_id: str,
    details: Dict[str, Any],
    reason: str = "",
    path: str = "audit.log",
) -> Dict[str, Any]:
    """Append a single event straight to the audit log file (for actions taken outside a full pipeline run, e.g. a UI approval decision)."""
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "event": event,
        "email_id": email_id,
        "details": details,
        "reason": reason,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    return entry
