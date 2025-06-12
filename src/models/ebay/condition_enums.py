from enum import IntEnum

__all__ = ["ConditionEnum"]

class ConditionEnum(IntEnum):
    """Enumeration of eBay item conditions.

    The numeric values correspond to eBay *conditionId*s used across the
    Inventory, Browse and Trading APIs.

    Source: `_archive/eBayConditionEnums.md`.

    | Name                       | ID   | Notes |
    |----------------------------|------|-------|
    | NEW                        | 1000 | Brand-new, unopened item in original packaging |
    | LIKE_NEW                   | 2750 | Opened but very lightly used (e.g. books/DVDs). For trading cards: *Graded* |
    | NEW_OTHER                  | 1500 | New, unused but may be missing original packaging or not sealed |
    | NEW_WITH_DEFECTS           | 1750 | New, unused but has defects (e.g. scuffs, missing buttons) |
    | USED_EXCELLENT             | 3000 | Used but in excellent condition. For apparel: *Pre-owned – Good* |
    | USED_VERY_GOOD             | 4000 | Used but in very good condition. For trading cards: *Ungraded* |
    | USED_GOOD                  | 5000 | Used but in good condition |
    | USED_ACCEPTABLE            | 6000 | Acceptable condition |
    | FOR_PARTS_OR_NOT_WORKING   | 7000 | Not fully functioning; suitable for repair or parts |
    | PRE_OWNED_EXCELLENT        | 2990 | Apparel categories only |
    | PRE_OWNED_FAIR             | 3010 | Apparel categories only |
    """

    NEW = 1000
    LIKE_NEW = 2750
    NEW_OTHER = 1500
    NEW_WITH_DEFECTS = 1750
    USED_EXCELLENT = 3000
    USED_VERY_GOOD = 4000
    USED_GOOD = 5000
    USED_ACCEPTABLE = 6000
    FOR_PARTS_OR_NOT_WORKING = 7000
    PRE_OWNED_EXCELLENT = 2990
    PRE_OWNED_FAIR = 3010

    @classmethod
    def from_id(cls, condition_id: int) -> "ConditionEnum":
        """Return the enum corresponding to *condition_id*.

        Raises
        ------
        ValueError
            If *condition_id* is not a valid eBay condition identifier.
        """
        try:
            return cls(condition_id)
        except ValueError as exc:
            raise ValueError(f"Unsupported eBay condition id: {condition_id}") from exc

    def __str__(self) -> str:  # pragma: no cover
        """Return the enumeration name for readability (e.g. ``"NEW"``)."""
        return self.name
