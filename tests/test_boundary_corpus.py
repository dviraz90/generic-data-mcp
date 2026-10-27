"""Runs the adversarial corpus in `evals/corpus/` against the validators.

`evals/run.py` produces the committed report; this file makes CI fail if any of
those numbers regress. Both read the same JSON case files, so there is no second
list of cases to keep in sync.
"""

import pytest

from evals.harness import load_cases, run_all, summarize

_TARGETS = ("sql", "identifier", "path")

# Run once at import so every case becomes its own test node — a failure names
# the offending case id rather than one opaque aggregate assertion.
_OUTCOMES = run_all()
_BY_ID = {o.case.id: o for o in _OUTCOMES}
_SUMMARY = summarize(_OUTCOMES)


@pytest.mark.parametrize("case_id", sorted(_BY_ID))
def test_case_behaves_as_specified(case_id):
    outcome = _BY_ID[case_id]
    case = outcome.case
    verb = "rejected" if case.should_reject else "accepted"
    got = "rejected" if outcome.rejected else "accepted"
    assert outcome.passed, (
        f"{case.id} ({case.cls}): expected to be {verb}, was {got}.\n"
        f"  input: {case.input!r}\n"
        f"  note:  {case.note}"
    )


def test_every_adversarial_input_is_rejected():
    assert _SUMMARY["adversarial_rejected"] == _SUMMARY["adversarial_cases"]


def test_every_legitimate_input_is_accepted():
    """A validator that rejects everything is broken, not safe."""
    assert _SUMMARY["legitimate_accepted"] == _SUMMARY["legitimate_cases"]


def test_rejections_use_the_documented_exception_type():
    """Tools surface errors for LLM recovery, so the type has to be ours.

    A raw third-party exception reaching ToolRegistry.call gets stringified as
    e.g. "TokenError: Error tokenizing ..." — which tells the model nothing about
    what to do next.
    """
    assert _SUMMARY["off_contract"] == []


@pytest.mark.parametrize("target", _TARGETS)
def test_corpus_covers_both_polarities(target):
    """Guards against a corpus that only ever asserts rejection."""
    cases = load_cases(target)
    assert any(c.should_reject for c in cases), f"{target}: no adversarial cases"
    assert any(not c.should_reject for c in cases), f"{target}: no legitimate cases"


def test_case_ids_are_unique():
    ids = [c.id for t in _TARGETS for c in load_cases(t)]
    assert len(ids) == len(set(ids))
