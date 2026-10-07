import pytest

from app import dice
from app.dice import DiceError, roll


def test_single_die_in_range():
    for _ in range(200):
        assert 1 <= roll("d20").total <= 20


def test_modifiers_and_multiple_terms(monkeypatch):
    monkeypatch.setattr(dice, "roll_die", lambda sides: sides)
    result = roll("2d6 + 1d8 - 3")
    assert result.total == 6 + 6 + 8 - 3
    assert [t.label for t in result.terms] == ["2d6", "1d8", "3"]


def test_negative_dice_term(monkeypatch):
    monkeypatch.setattr(dice, "roll_die", lambda sides: 2)
    assert roll("10-1d4").total == 8


def test_keep_highest_and_lowest(monkeypatch):
    values = iter([5, 17, 3, 12])
    monkeypatch.setattr(dice, "roll_die", lambda sides: next(values))
    assert roll("2d20kh1").total == 17
    assert roll("2d20kl1").total == 3


@pytest.mark.parametrize("expr", ["", "abc", "2d", "d1", "101d6", "2d20kh3", "1d6x", "1d6++2", "d6" + "+d6" * 25, "1d6>=7", "1d6>=0", "1d6>3"])
def test_invalid_expressions(expr):
    with pytest.raises(DiceError):
        roll(expr)


def test_terms_report_sides_and_d2_is_supported():
    result = roll("3d2+1")
    assert [t.sides for t in result.terms] == [2, None]
    assert all(v in (1, 2) for v in result.terms[0].rolls)


def test_success_target_counts_dice_meeting_it(monkeypatch):
    values = iter([1, 3, 4, 6, 2])
    monkeypatch.setattr(dice, "roll_die", lambda sides: next(values))
    result = roll("5d6>=3")
    term = result.terms[0]
    assert result.total == 3
    assert term.label == "5d6>=3"
    assert term.target == 3
    assert term.kept == [3, 4, 6]


def test_success_target_applies_after_keep(monkeypatch):
    values = iter([6, 2, 5])
    monkeypatch.setattr(dice, "roll_die", lambda sides: next(values))
    term = roll("3d6kh2>=6").terms[0]
    assert term.kept == [6]
    assert term.subtotal == 1
