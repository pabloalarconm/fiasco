"""Dice expression parser and roller.

Supported syntax (case-insensitive, whitespace ignored):
    d20            -> one twenty-sided die
    3d6+2          -> three d6 plus a flat modifier
    2d20kh1        -> roll 2d20, keep highest 1 (advantage)
    2d20kl1        -> roll 2d20, keep lowest 1 (disadvantage)
    4d6kh3+1d8-1   -> terms can be combined with + and -
    10d6>=3        -> count successes: dice showing 3 or more (Warhammer "3+")
"""

import re
import secrets
from dataclasses import dataclass, field

MAX_DICE_PER_TERM = 100
MAX_SIDES = 1000
MAX_TERMS = 20
MAX_EXPRESSION_LENGTH = 100

_TERM_RE = re.compile(r"([+-])?(?:(\d*)d(\d+)(?:(kh|kl)(\d+))?(?:>=(\d+))?|(\d+))")

_rng = secrets.SystemRandom()


class DiceError(ValueError):
    """Raised when a dice expression is invalid."""


@dataclass
class TermResult:
    sign: int
    label: str
    sides: int | None = None
    rolls: list[int] = field(default_factory=list)
    kept: list[int] = field(default_factory=list)
    target: int | None = None
    subtotal: int = 0

    def to_dict(self) -> dict:
        return {
            "sign": self.sign,
            "label": self.label,
            "sides": self.sides,
            "rolls": self.rolls,
            "kept": self.kept,
            "target": self.target,
            "subtotal": self.subtotal,
        }


@dataclass
class RollResult:
    expression: str
    terms: list[TermResult]
    total: int

    def to_dict(self) -> dict:
        return {
            "expression": self.expression,
            "terms": [t.to_dict() for t in self.terms],
            "total": self.total,
        }


def roll_die(sides: int) -> int:
    return _rng.randint(1, sides)


def roll(expression: str) -> RollResult:
    normalized = re.sub(r"\s+", "", expression or "").lower()
    if not normalized:
        raise DiceError("Empty expression")
    if len(normalized) > MAX_EXPRESSION_LENGTH:
        raise DiceError("Expression too long")

    terms: list[TermResult] = []
    pos = 0
    while pos < len(normalized):
        match = _TERM_RE.match(normalized, pos)
        if not match or match.end() == pos:
            raise DiceError(f"Invalid syntax near '{normalized[pos:]}'")
        # Every term after the first must be preceded by an explicit sign.
        if terms and match.group(1) is None:
            raise DiceError(f"Missing operator near '{normalized[pos:]}'")
        terms.append(_evaluate_term(match))
        if len(terms) > MAX_TERMS:
            raise DiceError(f"Too many terms (max {MAX_TERMS})")
        pos = match.end()

    total = sum(t.subtotal for t in terms)
    return RollResult(expression=normalized, terms=terms, total=total)


def _evaluate_term(match: re.Match) -> TermResult:
    sign_str, count_str, sides_str, keep_mode, keep_str, target_str, flat_str = match.groups()
    sign = -1 if sign_str == "-" else 1

    if flat_str is not None:
        value = int(flat_str)
        return TermResult(sign=sign, label=flat_str, subtotal=sign * value)

    count = int(count_str) if count_str else 1
    sides = int(sides_str)
    if not 1 <= count <= MAX_DICE_PER_TERM:
        raise DiceError(f"Dice count must be between 1 and {MAX_DICE_PER_TERM}")
    if not 2 <= sides <= MAX_SIDES:
        raise DiceError(f"Dice sides must be between 2 and {MAX_SIDES}")

    rolls = [roll_die(sides) for _ in range(count)]
    label = f"{count}d{sides}"
    kept = rolls

    if keep_mode:
        keep = int(keep_str)
        if not 1 <= keep <= count:
            raise DiceError("Keep amount must be between 1 and the number of dice")
        ordered = sorted(rolls, reverse=(keep_mode == "kh"))
        kept = ordered[:keep]
        label += f"{keep_mode}{keep}"

    if target_str is not None:
        target = int(target_str)
        if not 1 <= target <= sides:
            raise DiceError("Success target must be between 1 and the number of sides")
        # Only the dice that meet the target count, one point each.
        successes = [value for value in kept if value >= target]
        return TermResult(
            sign=sign,
            label=f"{label}>={target}",
            sides=sides,
            rolls=rolls,
            kept=successes,
            target=target,
            subtotal=sign * len(successes),
        )

    return TermResult(
        sign=sign,
        label=label,
        sides=sides,
        rolls=rolls,
        kept=kept,
        subtotal=sign * sum(kept),
    )
