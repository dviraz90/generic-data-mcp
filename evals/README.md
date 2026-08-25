# evals — boundary corpus

The README claims the server gives an agent SQL and keyword search over a directory
"with no code execution, no writes, and no path escape." That is a claim about this
repo's validators, so it can be measured directly. This directory measures it.

**No API key, no network, no model.** The run is deterministic and takes well under a
second.

## Running it

```bash
pip install -e ".[dev]"
python -m evals.run
```

```
python -m evals.run --verbose          # list every case outcome
python -m evals.run --out report.json   # additionally write a JSON report
```

Exit status is non-zero if any case behaved unexpectedly, so it works in a pipeline.

Nothing is written unless you ask for it, and no run output is committed. The run is
deterministic and takes under a second, and `tests/test_boundary_corpus.py` asserts the
same corpus on every push — so the reproduction is the artifact, and a checked-in copy
of the numbers would only go stale.

## What the numbers mean

```
adversarial inputs rejected : 39/39
legitimate inputs accepted  : 13/13
```

- **adversarial inputs rejected** — inputs marked `"expect": "reject"` that the
  validators refused. This is the security number.
- **legitimate inputs accepted** — inputs marked `"expect": "allow"` that passed.
  This is the number that keeps the first one honest: a validator that rejects
  *everything* would score 79/79 on the first line while being useless. Both must
  be perfect for the result to mean anything.
- **off-contract rejections** — inputs that were rejected, but by an exception type
  other than the one the validator documents (`SQLValidationError` /
  `PathValidationError`). These are not security failures — the input was still
  blocked — but they leak a third-party exception through an interface whose whole
  design goal is errors an LLM can recover from. The run lists them separately.

Per-class counts show which attack families are covered and how densely.

## What is being tested

| Target | Validator | Classes |
|---|---|---|
| SQL | `SQLValidator` (`src/validators/sql.py`) | `dml_insert`, `dml_update`, `dml_delete`, `dml_replace`, `dml_upsert`, `ddl_drop`, `ddl_create`, `ddl_alter`, `pragma`, `attach`, `maintenance`, `multi_statement`, `select_into`, `comment_smuggling`, `unparseable`, `empty` |
| Identifiers | `validate_identifier` (`src/validators/sql.py`) | `identifier_injection`, `identifier_shape` |
| Paths | `PathValidator` (`src/validators/path.py`) | `traversal`, `symlink`, `absolute`, `store_readback`, `path_shape` |

Path cases run against a real temporary directory tree — including an actual symlink
pointing out of the sandbox — because `PathValidator` resolves and then stats the
path. String-only cases would not exercise the resolve-before-check behaviour that
makes the guarantee hold.

## Layout

```
corpus/
  sql_cases.json          adversarial + legitimate SQL
  identifier_cases.json   injection and shape cases for table/column names
  path_cases.json         traversal, symlink, and escape cases
harness.py                loads and executes the corpus
run.py                    CLI
```

The corpus files are **data**, consumed by two things: `run.py`, which produces the
committed report, and `tests/test_boundary_corpus.py`, which fails CI if any of it
regresses. There is no second copy of the case list.

## Adding a case

Append to the relevant `corpus/*.json`:

```json
{"id": "sql-pragma-05", "class": "pragma", "expect": "reject",
 "input": "PRAGMA foreign_keys = OFF", "note": "why this matters"}
```

`id` must be unique across all three files. Path cases may use the placeholders
`{allowed}`, `{allowed2}`, `{outside}`, and `{db_path}`, substituted with real
temporary paths at run time.

Add `expect: "allow"` cases whenever you add a new rejection class — the corpus is
only as good as its false-positive coverage.

## The honest caveat

**This measures coverage of the attack classes we enumerated, not the absence of ones
we didn't.** A 100% rejection rate over a corpus written by the same person who wrote
the validators is evidence that the known cases are handled and that they stay handled
— it is not evidence that the server is safe. Security failures live in the tail, and
a corpus is by construction not the tail.

What it is good for: it makes the README's claim checkable by a stranger in about ten
seconds, it names exactly which classes are covered, and it turns a regression into a
red CI run instead of a silent hole.

Building this corpus found two real defects, both now fixed and covered:

- `SQLValidator` caught sqlglot's `ParseError` but not its sibling `TokenError`, so
  `'; DROP TABLE orders; --` was rejected with a raw third-party exception instead of a
  recovery-oriented message.
- `validate_identifier` anchored with `$`, which in Python also matches just before a
  trailing newline — so `"orders\n"` passed validation and was returned as a table name.
  Every current caller has a second gate that caught it, so it was not exploitable, but
  the validator was not enforcing the rule it documents.

That is the kind of thing this catches — not the kind of thing that proves absence.
