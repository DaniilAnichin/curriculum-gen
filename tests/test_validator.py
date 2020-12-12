from pathlib import Path

from timetable.validator import make_validator

ASSETS_DIR = Path(__file__).parent / 'assets'


def test_validator_toy(capsys):
    validator = make_validator(ASSETS_DIR / 'toy.in', ASSETS_DIR / 'toy.out')
    assert validator.total_violation_cost == 5
    assert validator.total_soft_cost == 30

    validator.print_violations()
    validator.print_costs()
    validator.print_total_cost()

    captured = capsys.readouterr()
    with open(ASSETS_DIR / 'toy.val') as out:
        assert captured.out == out.read()
