"""Utilities for normalizing and converting tabular data columns."""

from __future__ import annotations
import math
import unicodedata
from typing import Iterable, List, Optional, Tuple
import pandas as pd


_ID_KEYWORDS: Tuple[str, ...] = ("id",)
_CURRENCY_SYMBOLS: Tuple[str, ...] = ("$", "€", "£", "¥", "₽", "₱", "₹")


def normalize_column_name(name: object) -> str:
    """Return a normalized, accent-free column identifier."""
    if not isinstance(name, str):
        return ""
    normalized = unicodedata.normalize("NFKD", name.strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _strip_currency_symbols(value: str) -> str:
    cleaned = value
    for symbol in _CURRENCY_SYMBOLS:
        cleaned = cleaned.replace(symbol, "")
    return cleaned


def _coerce_to_string(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isnan(value) if isinstance(value, float) else False:
            return None
        return str(value)
    text = str(value).strip()
    return text or None


def _parse_numeric_text(text_value: object) -> Tuple[Optional[str], bool]:
    """Clean a numeric-like string and return (normalized_value, is_negative)."""
    text = _coerce_to_string(text_value)
    if text is None:
        return None, False

    cleaned = unicodedata.normalize("NFKC", text)
    cleaned = cleaned.replace("\xa0", "")
    cleaned = _strip_currency_symbols(cleaned)

    is_negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1]
        is_negative = True

    if cleaned.endswith("-"):
        cleaned = cleaned[:-1]
        is_negative = True

    if cleaned.startswith("-"):
        cleaned = cleaned[1:]
        is_negative = True

    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    cleaned = cleaned.replace(" ", "")

    if "." in cleaned and "," in cleaned:
        last_dot = cleaned.rfind(".")
        last_comma = cleaned.rfind(",")
        if last_dot > last_comma:
            cleaned = cleaned.replace(",", "")
        else:
            cleaned = cleaned.replace(".", "")
            cleaned = cleaned.replace(",", ".")
    elif cleaned.count(",") == 1 and len(cleaned.split(",")[1]) <= 2:
        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")

    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]

    cleaned = cleaned.replace("'", "")

    try:
        float(cleaned)
    except (TypeError, ValueError):
        return None, False

    return cleaned, is_negative


def is_numeric_like(text_value: object) -> bool:
    """Return True if a value can be safely interpreted as a number."""
    cleaned, _ = _parse_numeric_text(text_value)
    return cleaned is not None


def convert_numeric_text(text_value: object) -> Optional[float]:
    """Convert numeric-like text into a float. Returns pandas NA on failure."""
    if text_value is None:
        return pd.NA

    if isinstance(text_value, (int, float)) and not isinstance(text_value, bool):
        if isinstance(text_value, float) and math.isnan(text_value):
            return pd.NA
        return float(text_value)

    cleaned, is_negative = _parse_numeric_text(text_value)
    if cleaned is None:
        return pd.NA

    try:
        result = float(cleaned)
    except (TypeError, ValueError):
        return pd.NA

    return -result if is_negative else result


def _should_force_numeric(norm_column_name: str) -> bool:
    return any(keyword in norm_column_name for keyword in _ID_KEYWORDS)


def convert_text_columns_to_numbers(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Convert numeric-like object columns in ``df`` into numeric dtypes."""
    converted_columns: List[str] = []

    for column in df.columns:
        series = df[column]
        if pd.api.types.is_numeric_dtype(series):
            continue

        normalized_name = normalize_column_name(column)
        force_numeric = _should_force_numeric(normalized_name)

        if not (
            force_numeric
            or series.dtype == object
            or pd.api.types.is_string_dtype(series)
        ):
            continue

        non_null = series.dropna()
        if non_null.empty and not force_numeric:
            continue

        cleaned_non_null = non_null.map(_coerce_to_string).dropna()
        if cleaned_non_null.empty and not force_numeric:
            continue

        if force_numeric or cleaned_non_null.map(is_numeric_like).all():
            numeric_series = series.map(convert_numeric_text)
            df[column] = pd.to_numeric(numeric_series, errors="coerce")
            converted_columns.append(column)

    return df, converted_columns


def find_columns_with_keywords(
    columns: Iterable[str], keywords: Iterable[str]
) -> List[str]:
    """Return columns whose normalized name contains any of the provided keywords."""
    normalized_keywords = tuple(normalize_column_name(keyword) for keyword in keywords)
    matches: List[str] = []

    for column in columns:
        normalized_column = normalize_column_name(column)
        if any(
            keyword and keyword in normalized_column for keyword in normalized_keywords
        ):
            matches.append(column)

    return matches
