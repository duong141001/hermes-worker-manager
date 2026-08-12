import importlib.util
import json
from collections import Counter
from pathlib import Path


spec = importlib.util.spec_from_file_location("opaque_auto", Path(__file__).with_name("__init__.py"))
opaque = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(opaque)


def test_auto_sequential_never_repeats_previous_language():
    for seed in range(30):
        assert opaque.choose_auto_language("fr", seed=seed) in {"en", "ru"}


def test_auto_sequential_is_deterministic_for_a_seed():
    assert opaque.choose_auto_language("ru", seed=12345) == opaque.choose_auto_language("ru", seed=12345)


def test_auto_sequential_allows_the_only_available_locale():
    assert opaque.choose_auto_language("fr", seed=5, available_languages=["fr"]) == "fr"


def test_auto_parallel_assignments_are_balanced_and_deterministic():
    first = opaque.assign_auto_languages(8, seed=99)
    second = opaque.assign_auto_languages(8, seed=99)
    assert first == second
    counts = Counter(first)
    assert max(counts.values()) - min(counts.values()) <= 1
    assert set(first) <= {"en", "fr", "ru"}


def test_auto_parallel_respects_available_locales_and_balances_them():
    assigned = opaque.assign_auto_languages(7, seed=31, available_languages=["ru", "en"])
    counts = Counter(assigned)
    assert set(assigned) == {"en", "ru"}
    assert max(counts.values()) - min(counts.values()) <= 1


def test_auto_handoff_records_assigned_language_and_builds_that_language():
    result = json.loads(opaque.prepare_smit_handoff(
        action="review",
        entities=[{"type": "FORM"}],
        relations=["AUTO RANDOM LANGUAGE"],
        language="auto",
        seed=7,
        previous_language="en",
    ))
    assert result["language"] in {"fr", "ru"}
    assert result["requested_language"] == "auto"
    assert result["language"] != "en"
    assert "Review" not in result["goal"]


def test_auto_handoff_with_one_available_locale_records_auto_and_assignment():
    result = json.loads(opaque.prepare_smit_handoff(
        action="review",
        entities=[{"type": "LOCALE"}],
        language="auto",
        available_languages=["fr"],
        previous_language="fr",
        seed=17,
    ))
    assert result["ok"] is True
    assert result["requested_language"] == "auto"
    assert result["language"] == "fr"
    assert result["goal"].startswith("[SMIT_SANITIZED_V1] Examine")


if __name__ == "__main__":
    test_auto_sequential_never_repeats_previous_language()
    test_auto_sequential_is_deterministic_for_a_seed()
    test_auto_sequential_allows_the_only_available_locale()
    test_auto_parallel_assignments_are_balanced_and_deterministic()
    test_auto_parallel_respects_available_locales_and_balances_them()
    test_auto_handoff_records_assigned_language_and_builds_that_language()
    test_auto_handoff_with_one_available_locale_records_auto_and_assignment()
    print("AUTO_LANGUAGE_ASSERTIONS_OK")
