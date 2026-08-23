"""Runs the boundary corpus against the validators.

The corpus in `corpus/` is data; this module is the only thing that knows how to
execute it. Both consumers import from here — `evals/run.py` (writes the report)
and `tests/test_boundary_corpus.py` (fails CI on a regression) — so the case list
is never duplicated.

Nothing here calls a network service. The claims being measured are properties of
this repo's validators, so the whole run is deterministic and offline.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Iterator

from src.config import Config
from src.exceptions import PathValidationError, SQLValidationError
from src.validators.path import PathValidator
from src.validators.sql import SQLValidator, validate_identifier

CORPUS_DIR = Path(__file__).parent / "corpus"

# The exception each validator is *designed* to raise. A rejection through any
# other type still blocks the input, but it means the failure path isn't the one
# the code documents — the summary surfaces those separately rather than
# silently counting them as clean rejections.
_EXPECTED_ERRORS: dict[str, type[Exception]] = {
    "sql": SQLValidationError,
    "identifier": SQLValidationError,
    "path": PathValidationError,
}


@dataclass(frozen=True)
class Case:
    id: str
    cls: str
    expect: str  # "allow" | "reject"
    input: str
    note: str
    target: str  # "sql" | "identifier" | "path"

    @property
    def should_reject(self) -> bool:
        return self.expect == "reject"


@dataclass(frozen=True)
class Outcome:
    case: Case
    rejected: bool
    error_type: str | None
    error_message: str | None

    @property
    def passed(self) -> bool:
        return self.rejected == self.case.should_reject

    @property
    def off_contract(self) -> bool:
        """Rejected, but not via the validator's documented exception type."""
        if not self.rejected or self.error_type is None:
            return False
        return self.error_type != _EXPECTED_ERRORS[self.case.target].__name__

    def to_dict(self) -> dict:
        return {
            "id": self.case.id,
            "class": self.case.cls,
            "target": self.case.target,
            "expect": self.case.expect,
            "input": self.case.input,
            "note": self.case.note,
            "rejected": self.rejected,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "passed": self.passed,
            "off_contract": self.off_contract,
        }


def load_cases(target: str) -> list[Case]:
    raw = json.loads((CORPUS_DIR / f"{target}_cases.json").read_text())
    return [
        Case(
            id=c["id"],
            cls=c["class"],
            expect=c["expect"],
            input=c["input"],
            note=c["note"],
            target=target,
        )
        for c in raw
    ]


def _run(case: Case, action: Callable[[str], object]) -> Outcome:
    """Execute one case, recording whether the input was rejected and how."""
    try:
        action(case.input)
    except Exception as e:  # noqa: BLE001 — the type is the measurement
        return Outcome(case, rejected=True, error_type=type(e).__name__, error_message=str(e))
    return Outcome(case, rejected=False, error_type=None, error_message=None)


@dataclass(frozen=True)
class PathSandbox:
    """A real directory tree for the path cases.

    PathValidator checks `.exists()` and `.is_file()` after resolving, so these
    cases cannot be run against string paths alone — the traversal and symlink
    targets have to exist on disk for the test to mean anything.
    """

    validator: PathValidator
    substitutions: dict[str, str]

    def render(self, raw: str) -> str:
        return raw.format(**self.substitutions)


@contextmanager
def path_sandbox() -> Iterator[PathSandbox]:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        allowed = root / "allowed"
        allowed2 = root / "allowed2"
        outside = root / "outside"
        db_dir = root / "db"
        for d in (allowed, allowed2, outside, db_dir, allowed / "nested"):
            d.mkdir(parents=True)

        (allowed / "data.csv").write_text("a,b\n1,2\n")
        (allowed / "nested" / "deep.csv").write_text("a,b\n3,4\n")
        (allowed2 / "second.csv").write_text("a,b\n5,6\n")
        (outside / "secret.txt").write_text("classified\n")
        db_path = db_dir / "store.db"
        db_path.write_text("")

        # A symlink inside the sandbox pointing out of it, and a symlinked
        # directory — the two ways `..`-free traversal escapes a naive check.
        (allowed / "link_to_secret.txt").symlink_to(outside / "secret.txt")
        (allowed / "link_to_outside_dir").symlink_to(outside, target_is_directory=True)

        # Same invariant the server enforces at startup: the store must not sit
        # inside an ingest-allowed directory.
        Config(db_path=db_path.resolve(), allowed_dirs=(allowed.resolve(), allowed2.resolve()))

        yield PathSandbox(
            validator=PathValidator((allowed, allowed2)),
            substitutions={
                "allowed": str(allowed),
                "allowed2": str(allowed2),
                "outside": str(outside),
                "db_path": str(db_path),
            },
        )


def run_all() -> list[Outcome]:
    """Run every case in the corpus. Deterministic, offline, no API calls."""
    validator = SQLValidator()
    outcomes: list[Outcome] = []

    for case in load_cases("sql"):
        outcomes.append(_run(case, validator.validate))
    for case in load_cases("identifier"):
        outcomes.append(_run(case, validate_identifier))

    with path_sandbox() as sandbox:
        for case in load_cases("path"):
            rendered = Case(
                id=case.id,
                cls=case.cls,
                expect=case.expect,
                input=sandbox.render(case.input),
                note=case.note,
                target=case.target,
            )
            outcomes.append(_run(rendered, sandbox.validator.validate))

    return outcomes


def summarize(outcomes: list[Outcome]) -> dict:
    by_class: dict[str, dict[str, int]] = {}
    for o in outcomes:
        bucket = by_class.setdefault(
            o.case.cls, {"total": 0, "passed": 0, "rejected": 0, "allowed": 0}
        )
        bucket["total"] += 1
        bucket["passed"] += int(o.passed)
        bucket["rejected"] += int(o.rejected)
        bucket["allowed"] += int(not o.rejected)

    adversarial = [o for o in outcomes if o.case.should_reject]
    legitimate = [o for o in outcomes if not o.case.should_reject]

    return {
        "total_cases": len(outcomes),
        "adversarial_cases": len(adversarial),
        "adversarial_rejected": sum(o.rejected for o in adversarial),
        "legitimate_cases": len(legitimate),
        "legitimate_accepted": sum(not o.rejected for o in legitimate),
        "failures": [o.case.id for o in outcomes if not o.passed],
        "off_contract": [o.case.id for o in outcomes if o.off_contract],
        "classes": dict(sorted(by_class.items())),
    }
