"""Pure comparison of dated live key-listing snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def compare_key_cohorts(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Compare parent counters only; never call the delta completed sales."""
    if previous.get("source") != "eBay Browse active UK listings" or current.get("source") != previous.get("source"):
        raise ValueError("Both inputs must be Browse key-cohort snapshots.")
    if previous.get("series") != current.get("series"):
        raise ValueError("Snapshots must be for the same key series.")
    earlier = datetime.fromisoformat(previous["captured_at"].replace("Z", "+00:00"))
    later = datetime.fromisoformat(current["captured_at"].replace("Z", "+00:00"))
    if later <= earlier:
        raise ValueError("Current snapshot must be captured after previous snapshot.")
    old = {str(item["parent_item_id"]): item for item in previous.get("parents", [])}
    new = {str(item["parent_item_id"]): item for item in current.get("parents", [])}
    rows = []
    for item_id in sorted(old.keys() | new.keys()):
        before, after = old.get(item_id), new.get(item_id)
        before_sold = before.get("quantity_sold") if before else None
        after_sold = after.get("quantity_sold") if after else None
        delta = None
        if isinstance(before_sold, int) and isinstance(after_sold, int) and after_sold >= before_sold:
            delta = after_sold - before_sold
        rows.append({
            "parent_item_id": item_id,
            "status": "both" if before and after else "new" if after else "absent_from_current_search",
            "previous_cumulative_sold": before_sold,
            "current_cumulative_sold": after_sold,
            "cumulative_sold_delta_proxy": delta,
            "possible_exact_codes": (after or before or {}).get("possible_exact_codes", []),
            "asking_price_previous": before.get("asking_price") if before else None,
            "asking_price_current": after.get("asking_price") if after else None,
        })
    return {
        "source": "Comparison of eBay Browse active UK listing snapshots",
        "series": current["series"], "previous_captured_at": previous["captured_at"],
        "current_captured_at": current["captured_at"], "parents": rows,
        "limitations": [
            "Counter growth is a proxy for activity, not completed-order evidence or a same-code sale.",
            "A parent missing from current search may still be active, ended or relisted; investigate separately.",
            "Variation-level demand requires dated order or Product Research evidence.",
        ],
    }
