from pathlib import Path

import pytest

from timetable.validator import make_validator

ASSETS_DIR = Path(__file__).parent / 'assets'


@pytest.mark.parametrize(
    "in_path, out_path, val_path, violation_cost, soft_cost",
    [
        ('toy.in', 'toy.out', 'toy.val', 5, 30),
        ('toy.in', 'perfect.out', 'perfect.val', 0, 0),
    ]
)
def test_validator_toy(capsys, in_path, out_path, val_path, violation_cost, soft_cost):
    with open(ASSETS_DIR / in_path) as faculty_input, open(ASSETS_DIR / out_path) as timetable_input:
        validator = make_validator(faculty_input, timetable_input)
    assert validator.total_violation_cost == violation_cost
    assert validator.total_soft_cost == soft_cost

    validator.print_violations()
    validator.print_costs()
    validator.print_total_cost()

    captured = capsys.readouterr()
    with open(ASSETS_DIR / val_path) as out:
        assert captured.out == out.read()
