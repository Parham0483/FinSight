"""CSV auto-detection: column headers in different order, different names,
different languages, and locale-varied number/date formats must all import
without a manual column_map, or fail with a specific, actionable error —
never a generic/opaque one. Money-handling risk-based coverage: decimal
parsing correctness across locales is exactly the kind of expensive-to-get-
wrong logic the testing bar exists for.
"""
from decimal import Decimal

import pytest

from apps.transactions.ingestion.csv_import import (
    CsvImportSource,
    _parse_decimal,
    detect_column_map,
)
from apps.transactions.models import Transaction

pytestmark = pytest.mark.unit


# ── detect_column_map: header matching ──────────────────────────────────

def test_detects_standard_english_headers():
    cm = detect_column_map(['date', 'description', 'amount', 'currency'])
    assert cm == {'date': 'date', 'description': 'description', 'amount': 'amount', 'currency': 'currency'}


def test_detects_headers_regardless_of_order():
    cm = detect_column_map(['currency', 'amount', 'date', 'description'])
    assert cm['date'] == 'date'
    assert cm['amount'] == 'amount'


def test_detects_deposits_withdrawls_layout():
    # The real downloaded bank-statement test file uses this exact (misspelled)
    # layout: Date, Description, Deposits, Withdrawls, Balance.
    cm = detect_column_map(['Date', 'Description', 'Deposits', 'Withdrawls', 'Balance'])
    assert cm['date'] == 'Date'
    assert cm['description'] == 'Description'
    assert cm['credit'] == 'Deposits'
    assert cm['debit'] == 'Withdrawls'
    assert cm['balance'] == 'Balance'


def test_detects_credit_debit_type_layout():
    cm = detect_column_map(['transaction_id', 'date', 'customer_id', 'amount', 'type', 'description'])
    assert cm['date'] == 'date'
    assert cm['amount'] == 'amount'
    assert cm['description'] == 'description'


@pytest.mark.parametrize('headers,expected', [
    (['Fecha', 'Descripcion', 'Monto', 'Moneda'], {'date': 'Fecha', 'description': 'Descripcion', 'amount': 'Monto', 'currency': 'Moneda'}),
    (['Datum', 'Beschreibung', 'Betrag'], {'date': 'Datum', 'description': 'Beschreibung', 'amount': 'Betrag'}),
    (['Date', 'Libelle', 'Montant'], {'date': 'Date', 'description': 'Libelle', 'amount': 'Montant'}),
    (['Data', 'Descrizione', 'Importo'], {'date': 'Data', 'description': 'Descrizione', 'amount': 'Importo'}),
])
def test_detects_headers_in_other_latin_script_languages(headers, expected):
    cm = detect_column_map(headers)
    for field, header in expected.items():
        assert cm[field] == header


def test_detects_arabic_headers():
    cm = detect_column_map(['التاريخ', 'الوصف', 'المبلغ'])
    assert cm['date'] == 'التاريخ'
    assert cm['description'] == 'الوصف'
    assert cm['amount'] == 'المبلغ'


def test_fuzzy_matches_near_miss_spelling():
    # "Withdrawls" (missing an 'a') is an exact alias already; test a header
    # that's a genuine near-miss NOT in the alias list verbatim.
    cm = detect_column_map(['Date', 'Descriptio', 'Amoutn'])  # typos not in alias table
    assert cm.get('date') == 'Date'
    # Fuzzy fallback should still resolve these close-but-not-exact headers.
    assert cm.get('description') == 'Descriptio'
    assert cm.get('amount') == 'Amoutn'


def test_unrecognisable_headers_produce_no_mapping_for_that_field():
    cm = detect_column_map(['xyz123', 'foo', 'bar'])
    assert cm == {}


# ── CsvImportSource: auto-detect end to end ─────────────────────────────

@pytest.mark.django_db
def test_auto_detect_imports_signed_amount_layout(org):
    content = 'Fecha,Descripcion,Monto\n2026-01-01,Cafe,-50.00\n2026-01-02,Pago cliente,500.00\n'
    result = CsvImportSource(org, content=content).sync()
    assert result.created == 2
    amounts = set(Transaction.objects.filter(org=org).values_list('amount', flat=True))
    assert amounts == {Decimal('-50.00'), Decimal('500.00')}


@pytest.mark.django_db
def test_auto_detect_imports_deposits_withdrawls_layout(org):
    content = (
        'Date,Description,Deposits,Withdrawls,Balance\n'
        '20-Aug-2020,Cheque,"582,827.75",00.00,"609,730.09"\n'
        '20-Aug-2020,Tax,00.00,"50,810.84","304,865.05"\n'
    )
    result = CsvImportSource(org, content=content).sync()
    assert result.created == 2
    amounts = set(Transaction.objects.filter(org=org).values_list('amount', flat=True))
    assert amounts == {Decimal('582827.75'), Decimal('-50810.84')}


@pytest.mark.django_db
def test_auto_detect_column_order_does_not_matter(org):
    content = 'Amount,Date,Description\n12.50,2026-03-03,Stuff\n'
    result = CsvImportSource(org, content=content).sync()
    assert result.created == 1
    assert Transaction.objects.get(org=org).amount == Decimal('12.50')


@pytest.mark.django_db
def test_auto_detect_raises_specific_error_for_unrecognised_layout(org):
    content = 'xyz123,foo,bar\n1,2,3\n'
    with pytest.raises(ValueError) as exc_info:
        CsvImportSource(org, content=content).sync()
    message = str(exc_info.value)
    assert 'date' in message
    assert 'xyz123' in message  # names the actual columns found, not a generic failure
    assert 'foo' in message and 'bar' in message


@pytest.mark.django_db
def test_auto_detect_raises_when_only_amount_missing(org):
    content = 'Date,Description\n2026-01-01,Something\n'
    with pytest.raises(ValueError, match='amount'):
        CsvImportSource(org, content=content).sync()


# ── Explicit preset/column_map paths remain backward compatible ─────────

@pytest.mark.django_db
def test_explicit_preset_still_takes_priority_over_auto_detect(org):
    # A CSV whose real headers WOULD auto-detect differently must still obey
    # an explicitly passed preset/column_map — auto-detect only applies when
    # neither is given.
    content = 'date,description,amount,currency\n2026-01-01,X,1.00,GBP\n'
    result = CsvImportSource(org, content=content, preset='generic_signed').sync()
    assert result.created == 1


def test_missing_date_column_still_raises_expected_message_with_explicit_preset():
    # Regression: apps/transactions/tests/test_ingestion.py has an existing
    # test expecting the substring 'missing the "date" column' from the
    # EXPLICIT column_map/preset validation path — must not regress that
    # wording while generalising validation to all mapped columns. No DB
    # access happens before the raise, so no org/db fixture is needed.
    content = 'wrong,header\n1,2\n'
    with pytest.raises(ValueError, match='missing the "date" column'):
        CsvImportSource(None, content=content, preset='generic_signed').fetch()


# ── _parse_decimal: locale-tolerant number parsing ───────────────────────

@pytest.mark.parametrize('raw,expected', [
    ('582,827.75', Decimal('582827.75')),     # US/UK thousands+decimal
    ('1.234,56', Decimal('1234.56')),          # European thousands+decimal
    ('1234,56', Decimal('1234.56')),           # European decimal only
    ('1,234', Decimal('1234')),                # thousands only, no decimal
    ('00.00', Decimal('0.00')),
    ('(500.00)', Decimal('-500.00')),          # accounting negative
    ('-500.00', Decimal('-500.00')),
    ('£1,200.50', Decimal('1200.50')),
    ('$1,200.50', Decimal('1200.50')),
    ('USD 100.00', Decimal('100.00')),
    ('100.00 EUR', Decimal('100.00')),
    ('', Decimal('0')),
    ('   ', Decimal('0')),
])
def test_parse_decimal_handles_locale_variants(raw, expected):
    assert _parse_decimal(raw) == expected


def test_parse_decimal_raises_on_genuinely_invalid_value():
    with pytest.raises(ValueError, match='Invalid amount'):
        _parse_decimal('not a number')
