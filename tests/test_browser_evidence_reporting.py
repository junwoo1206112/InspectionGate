"""Behavioral regression for complete, non-vacuous UI and axe evidence."""

from copy import deepcopy

from scripts import axe_audit, ui_checks


def axe_states():
    return [{"state": state, "axe_version": "4.13.0", "tags": axe_audit.TAGS,
             "violation_count": 0, "incomplete_count": 0, "pass_count": 24, "violations": []}
            for state in axe_audit.EXPECTED_STATES]


def test_ui_requires_exact_checks_and_passed_status():
    good = [{"name": name, "status": "passed"} for name in ui_checks.REQUIRED_CHECKS]
    assert ui_checks.report_status(good) == "passed"
    for bad in ([], good[:-1], good + [good[0]], [good[0]] * len(good)):
        assert ui_checks.report_status(bad) == "failed"
    failed = deepcopy(good)
    failed[0]["status"] = "failed"
    assert ui_checks.report_status(failed) == "failed"


def test_axe_requires_all_states_and_executed_rules():
    good = axe_states()
    assert axe_audit.aggregate_status(good) == "passed"
    for bad in ([], good[:-1], good + [good[0]], [good[0]] * 5):
        assert axe_audit.aggregate_status(bad) == "failed"
    for field, value in (("pass_count", 0), ("violation_count", -1), ("incomplete_count", True),
                         ("axe_version", ""), ("tags", [])):
        bad = deepcopy(good)
        bad[0][field] = value
        assert axe_audit.aggregate_status(bad) == "failed"


def test_axe_incomplete_is_review_required_and_violations_or_errors_fail():
    states = axe_states()
    states[0]["incomplete_count"] = 1
    assert axe_audit.aggregate_status(states) == "needs_review"
    states[1]["violation_count"] = 1
    states[1]["violations"] = [{"id": "color-contrast"}]
    assert axe_audit.aggregate_status(states) == "failed"
    assert axe_audit.aggregate_status(axe_states(), [{"stage": "timeout"}]) == "failed"
