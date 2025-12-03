from src import app as app_module


def test_rejects_invalid_signature(tmp_path):
    """Files with non-Excel signatures should be blocked early."""
    bogus_excel = tmp_path / "malicious.xlsx"
    bogus_excel.write_text("not really an excel file", encoding="utf-8")

    assert app_module.is_valid_excel_file(str(bogus_excel)) is False


def test_rejects_empty_file(tmp_path):
    """Empty uploads fail validation."""
    empty_excel = tmp_path / "empty.xlsx"
    empty_excel.touch()

    assert app_module.is_valid_excel_file(str(empty_excel)) is False


def test_rejects_oversized_file(tmp_path, monkeypatch):
    """Respect the MAX_CONTENT_LENGTH guardrail for large uploads."""
    oversized_limit = 10
    monkeypatch.setattr(app_module, "MAX_CONTENT_LENGTH", oversized_limit)
    monkeypatch.setitem(app_module.app.config, "MAX_CONTENT_LENGTH", oversized_limit)

    large_excel = tmp_path / "huge.xlsx"
    large_excel.write_bytes(
        b"PK\x03\x040" * 4
    )  # Valid ZIP header repeated; file > limit

    assert app_module.is_valid_excel_file(str(large_excel)) is False
