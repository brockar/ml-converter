import pandas as pd
import pytest

from src import converters


def test_converts_currency_strings_to_numbers():
    df = pd.DataFrame(
        {
            'Monto Neto de Operacion': ['\u20ac1.234,56', '$ 1,234.56', '(1.234,56)'],
            'descripcion': ['uno', 'dos', 'tres'],
        }
    )

    processed, converted = converters.convert_text_columns_to_numbers(df)

    assert 'Monto Neto de Operacion' in converted
    assert processed['Monto Neto de Operacion'].iloc[0] == pytest.approx(1234.56)
    assert processed['Monto Neto de Operacion'].iloc[1] == pytest.approx(1234.56)
    assert processed['Monto Neto de Operacion'].iloc[2] == pytest.approx(-1234.56)


def test_force_converts_id_columns_even_with_padding():
    df = pd.DataFrame(
        {
            'Operacion ID': ['000123', ' 456 ', None],
        }
    )

    processed, converted = converters.convert_text_columns_to_numbers(df)

    assert 'Operacion ID' in converted
    assert processed['Operacion ID'].dropna().tolist() == [123.0, 456.0]


def test_mixed_content_column_is_not_converted():
    df = pd.DataFrame(
        {
            'monto': ['$123', 'no aplicar', '$456'],
        }
    )

    processed, converted = converters.convert_text_columns_to_numbers(df)

    assert 'monto' not in converted
    assert processed['monto'].dtype == object


def test_convert_numeric_text_returns_na_for_invalid_strings():
    assert pd.isna(converters.convert_numeric_text('no es numero'))
