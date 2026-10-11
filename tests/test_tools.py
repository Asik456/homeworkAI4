import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import calculate, lookup, run_tool


def test_lookup_finds_2025_population():
    result = lookup("Tarnvale", "population_2025")
    assert result["value"] == 71388
    assert result["source"] == "NR-03"


def test_lookup_misspelled_name():
    result = lookup("Ossbrige", "area_km2")
    assert "error" in result
    assert "Ossbridge" in result["error"]


def test_lookup_similar_names_are_not_mixed():
    assert lookup("Ossbridge", "area_km2")["value"] == 1284.6
    assert lookup("Ossford", "area_km2")["value"] == 846.2


def test_lookup_skips_archived_profile():
    result = lookup("Kelmarsh", "population_2025")
    assert result["value"] == 24117
    assert result["source"] == "NR-04"
    assert lookup("Tarnvale", "schools")["value"] == 29


def test_lookup_applies_correction():
    result = lookup("Brightwater", "area_km2")
    assert result["value"] == 921.4
    assert "NR-16" in result["source"]


def test_lookup_converts_cubic_metres():
    result = lookup("Lindenmoor", "water_megalitres")
    assert result["value"] == 2151.4
    assert result["unit"] == "megalitres"


def test_lookup_unknown_field_and_district():
    assert "error" in lookup("Redfen", "size")
    assert "error" in lookup("Paris", "area_km2")


def test_lookup_bad_input_does_not_crash():
    assert "error" in lookup(None, "area_km2")
    assert "error" in run_tool("lookup", "not json")
    assert "error" in run_tool("lookup", '{"district": "Redfen"}')


def test_calculate_multiplication():
    assert abs(calculate("48317 * 1.0947")["result"] - 52892.6199) < 1e-6


def test_calculate_refuses_import():
    result = calculate("__import__('os').system('echo hi')")
    assert "error" in result


def test_calculate_refuses_class():
    assert "error" in calculate("(1).__class__")


def test_calculate_refuses_huge_power_fast():
    start = time.perf_counter()
    result = calculate("9**9**9")
    assert "error" in result
    assert time.perf_counter() - start < 1


def test_calculate_division_by_zero():
    assert calculate("5 / 0") == {"error": "division by zero"}


def test_calculate_brackets_and_order():
    assert calculate("(2 + 3) * 4 - 2 ** 3")["result"] == 12


def test_calculate_bad_syntax_and_commas():
    assert "error" in calculate("2 +* 3")
    assert "error" in calculate("44,675 / 2")
