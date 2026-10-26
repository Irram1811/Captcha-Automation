import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "measure_rates.py"
SPEC = importlib.util.spec_from_file_location("measure_rates", SCRIPT)
assert SPEC and SPEC.loader
measure_rates = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measure_rates)


def test_measurements_merge_by_widget_and_classifier():
    previous = {
        "rows": [
            {"widget": "slider", "classifier": "—", "runs": 20},
            {"widget": "image_grid", "classifier": "fake", "runs": 20},
        ],
        "records": [
            {"widget": "slider", "classifier": "—", "seed": 1, "verdict": "PASS"},
            {"widget": "image_grid", "classifier": "fake", "seed": 1, "verdict": "PASS"},
        ],
    }
    rows, records = measure_rates._merge_measurements(
        previous,
        [{"widget": "slider", "classifier": "—", "runs": 5, "successes": 4}],
        [{"widget": "slider", "classifier": "—", "seed": 9, "verdict": "FAIL"}],
    )
    assert {(row["widget"], row["classifier"]) for row in rows} == {
        ("slider", "—"),
        ("image_grid", "fake"),
    }
    assert next(row for row in rows if row["widget"] == "slider")["runs"] == 5
    assert {(record["widget"], record["seed"]) for record in records} == {
        ("slider", 1),
        ("slider", 9),
        ("image_grid", 1),
    }
