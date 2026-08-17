import openpyxl
from src.parsers.xlsx import XLSXParser


def _write_workbook(path, rows):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_parses_header_and_rows_as_strings(tmp_path):
    xlsx_path = tmp_path / "orders.xlsx"
    _write_workbook(
        xlsx_path,
        [
            ["id", "customer", "amount", "active"],
            [1, "Alice", 10.5, True],
            [2, "Bob", 20, False],
        ],
    )

    rows = list(XLSXParser().parse(xlsx_path))

    assert rows == [
        {"id": "1", "customer": "Alice", "amount": "10.5", "active": "true"},
        {"id": "2", "customer": "Bob", "amount": "20", "active": "false"},
    ]
    for row in rows:
        for value in row.values():
            assert isinstance(value, str)


def test_none_cells_become_empty_string(tmp_path):
    xlsx_path = tmp_path / "gaps.xlsx"
    _write_workbook(
        xlsx_path,
        [
            ["id", "note"],
            [1, None],
        ],
    )

    rows = list(XLSXParser().parse(xlsx_path))

    assert rows == [{"id": "1", "note": ""}]


def test_trailing_empty_rows_are_skipped(tmp_path):
    xlsx_path = tmp_path / "trailing.xlsx"
    _write_workbook(
        xlsx_path,
        [
            ["id", "customer"],
            [1, "Alice"],
            [None, None],
            [None, None],
        ],
    )

    rows = list(XLSXParser().parse(xlsx_path))

    assert rows == [{"id": "1", "customer": "Alice"}]


def test_empty_sheet_raises_parse_error(tmp_path):
    from src.exceptions import ParseError  # noqa: PLC0415 - lazy: optional [ui] dependency

    xlsx_path = tmp_path / "empty.xlsx"
    _write_workbook(xlsx_path, [])

    parser = XLSXParser()
    try:
        list(parser.parse(xlsx_path))
    except ParseError:
        pass
    else:
        raise AssertionError("Expected ParseError for an empty sheet")
