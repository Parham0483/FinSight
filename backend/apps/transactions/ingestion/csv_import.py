"""CSV bank-statement import.

The blueprint (§5) ships CSV import *before* bank-integration polish — it is
the fastest path to real data and the demo backbone. Banks export wildly
different column layouts, so this adapter takes a ``column_map`` (or a named
preset) describing which CSV headers map to our normalised fields, plus a
couple of presets for common UK/US layouts.

Amount handling supports the two conventions banks use:
  * a single signed ``amount`` column, or
  * separate ``debit``/``credit`` columns (debit → outflow, credit → inflow).

Column detection: when no ``preset`` or explicit ``column_map`` is given,
this adapter auto-detects columns from the CSV's own header row using a
multilingual alias table (English, Spanish, French, German, Italian,
Portuguese, Turkish, Arabic — extending to more languages is a matter of
adding entries to ``_ALIASES``, not restructuring anything) plus a
fuzzy-match fallback for near-miss/typo'd headers (e.g. a real downloaded
bank export spelling "Withdrawals" as "Withdrawls"). This means:
  - column ORDER never matters — everything is header-keyed, never positional
  - column NAMES can differ across banks/languages without a manual mapping
  - an unrecognised layout fails with a specific, actionable error naming
    exactly which required field(s) couldn't be identified and what headers
    the file actually has — never a generic/opaque failure.

Not handled (deliberately out of scope, flagged rather than silently
half-done): translating/localising the *values* inside description cells,
or non-Latin/localised month names inside date values (e.g. Spanish "Ago"
for August) — only column *headers* get multilingual treatment. Date
*values* rely on ISO/common numeric formats plus English month
abbreviations/names.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import datetime, time, timezone
from decimal import Decimal, InvalidOperation
from difflib import get_close_matches
from typing import Any, Iterable

from django.utils.dateparse import parse_date, parse_datetime

from .base import IngestionSource, NormalizedTransaction
from ..models import Transaction


# Named presets: friendly preset name → column_map. Users can also pass a raw
# column_map for any layout we don't have a preset for, or omit both and let
# auto-detection (see `detect_column_map`) figure it out from the headers.
CSV_PRESETS: dict[str, dict[str, str]] = {
    'generic_signed': {
        'date': 'date',
        'description': 'description',
        'amount': 'amount',
        'currency': 'currency',
    },
    'generic_debit_credit': {
        'date': 'date',
        'description': 'description',
        'debit': 'debit',
        'credit': 'credit',
    },
    'starling': {
        'date': 'Date',
        'description': 'Reference',
        'counterparty': 'Counter Party',
        'amount': 'Amount (GBP)',
    },
    'wise': {
        'date': 'Date',
        'description': 'Description',
        'amount': 'Amount',
        'currency': 'Currency',
        'counterparty': 'Payee Name',
    },
}

_DATE_FORMATS = (
    '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%d %b %Y', '%d/%m/%y',
    '%d-%b-%Y', '%d-%b-%y', '%d %B %Y', '%b %d, %Y', '%B %d, %Y',
)


def _parse_date(value: str) -> datetime:
    value = (value or '').strip()
    if not value:
        raise ValueError('Missing date.')
    # Try ISO datetime, then ISO date, then common bank formats.
    dt = parse_datetime(value)
    if dt is not None:
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    d = parse_date(value)
    if d is not None:
        return datetime.combine(d, time.min, tzinfo=timezone.utc)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f'Unrecognised date format: {value!r}')


_CURRENCY_SYMBOLS_RE = re.compile(r'[£$€¥₹₺₩₪]')
# A standalone 3-letter alpha token at either end (e.g. "USD 100.00", "100.00 EUR")
# — an ISO 4217 code, not part of the number itself.
_ISO_CODE_RE = re.compile(r'^[A-Za-z]{3}\s+|\s+[A-Za-z]{3}$')


def _parse_decimal(value: str) -> Decimal:
    """Locale-tolerant decimal parsing: handles US/UK (1,234.56), European
    (1.234,56 or 1234,56), accounting-negative "(500.00)", currency symbols,
    and standalone ISO currency codes ("USD 100.00").
    """
    cleaned = (value or '').strip()
    if not cleaned:
        return Decimal('0')

    cleaned = _CURRENCY_SYMBOLS_RE.sub('', cleaned)
    cleaned = _ISO_CODE_RE.sub('', cleaned).strip()
    cleaned = cleaned.replace(' ', '')

    negative = False
    if cleaned.startswith('(') and cleaned.endswith(')'):
        negative = True
        cleaned = cleaned[1:-1]
    if cleaned.startswith('-'):
        negative = True
        cleaned = cleaned[1:]

    if ',' in cleaned and '.' in cleaned:
        if cleaned.rfind(',') > cleaned.rfind('.'):
            # European: '.' is the thousands separator, ',' is decimal (1.234,56).
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            # US/UK: ',' is the thousands separator, '.' is decimal (1,234.56).
            cleaned = cleaned.replace(',', '')
    elif ',' in cleaned:
        # Only a comma: one comma followed by 1-2 digits reads as a European
        # decimal separator (1234,56); anything else is a thousands separator.
        parts = cleaned.split(',')
        if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
            cleaned = cleaned.replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
    # else: only '.' or no separator at all — already Decimal-parseable.

    if not cleaned:
        return Decimal('0')
    try:
        result = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f'Invalid amount: {value!r}') from exc
    return -result if negative else result


# Canonical field -> known header aliases across languages. Duplicate literal
# strings across two different fields' sets would be ambiguous — there are
# none; each alias belongs to exactly one canonical field.
_ALIASES: dict[str, set[str]] = {
    'date': {
        'date', 'transaction date', 'txn date', 'posting date', 'value date',
        'fecha', 'fecha de transaccion', 'fecha de la transaccion',
        'date de transaction', 'date operation', 'date d operation',
        'datum', 'buchungsdatum', 'transaktionsdatum',
        'data', 'data operazione', 'data transazione',
        'data da transacao', 'data de transacao',
        'islem tarihi', 'tarih',
        'التاريخ', 'تاريخ العملية', 'تاريخ المعاملة',
    },
    'description': {
        'description', 'narration', 'details', 'memo', 'reference', 'particulars',
        'descripcion', 'concepto', 'detalle',
        'libelle',
        'beschreibung', 'verwendungszweck', 'buchungstext',
        'descrizione', 'causale',
        'historico',
        'aciklama',
        'الوصف', 'البيان', 'التفاصيل',
    },
    'amount': {
        'amount', 'value', 'transaction amount', 'amt',
        'monto', 'importe', 'cantidad',
        'montant',
        'betrag',
        'importo',
        'valor',
        'tutar', 'miktar',
        'المبلغ', 'القيمة',
    },
    'debit': {
        'debit', 'withdrawal', 'withdrawals', 'withdrawls', 'money out', 'outflow', 'paid out',
        'debito', 'cargo', 'salida',
        'sortie',
        'lastschrift', 'belastung', 'soll',
        'addebito', 'uscita',
        'saida',
        'borc', 'cikis',
        'مدين', 'سحب', 'خصم',
    },
    'credit': {
        'credit', 'deposit', 'deposits', 'money in', 'inflow', 'paid in',
        'credito', 'abono', 'entrada',
        'entree',
        'gutschrift', 'haben',
        'accredito', 'entrata',
        'alacak', 'giris',
        'دائن', 'إيداع',
    },
    'currency': {
        'currency', 'ccy', 'curr',
        'moneda', 'divisa',
        'devise',
        'wahrung',
        'valuta',
        'moeda',
        'para birimi', 'doviz',
        'العملة',
    },
    'counterparty': {
        'counterparty', 'counter party', 'payee', 'payer', 'merchant', 'beneficiary', 'other party',
        'contraparte', 'beneficiario',
        'contrepartie', 'beneficiaire',
        'gegenpartei', 'empfanger',
        'controparte',
        'karsi taraf', 'alici',
        'الطرف المقابل', 'المستفيد',
    },
    'balance': {
        'balance', 'running balance', 'closing balance',
        'saldo',
        'solde',
        'kontostand',
        'bakiye',
        'الرصيد',
    },
}

# Required for a usable mapping: 'date' plus either 'amount' or a debit/credit pair.
_REQUIRED_ALONE = ('date',)
_REQUIRED_ONE_OF = ('amount', 'debit', 'credit')


def _normalise_header(header: str) -> str:
    """Lowercase, strip accents/diacritics (é→e, ü→u — Latin-script languages
    only; Arabic and other non-Latin scripts pass through unaffected and are
    compared as-is), collapse punctuation/whitespace variants.
    """
    header = header.strip().lower()
    header = unicodedata.normalize('NFKD', header)
    header = ''.join(ch for ch in header if not unicodedata.combining(ch))
    header = re.sub(r'[^\w]+', ' ', header, flags=re.UNICODE).strip()
    return header


_NORMALISED_ALIASES: dict[str, str] = {
    _normalise_header(alias): field
    for field, aliases in _ALIASES.items()
    for alias in aliases
}
_FUZZY_CUTOFF = 0.82


def detect_column_map(fieldnames: list[str]) -> dict[str, str]:
    """Best-effort header → canonical field mapping via exact alias match
    (after normalisation), falling back to fuzzy matching against the alias
    table for near-miss spellings. Returns canonical_field -> actual header
    text, only for fields it could identify — callers check which required
    fields are still missing and raise a specific error, never a silent gap.
    """
    column_map: dict[str, str] = {}
    alias_keys = list(_NORMALISED_ALIASES.keys())
    for header in fieldnames:
        norm = _normalise_header(header)
        field = _NORMALISED_ALIASES.get(norm)
        if field is None:
            close = get_close_matches(norm, alias_keys, n=1, cutoff=_FUZZY_CUTOFF)
            if close:
                field = _NORMALISED_ALIASES[close[0]]
        if field and field not in column_map:  # first matching header wins
            column_map[field] = header
    return column_map


class CsvImportSource(IngestionSource):
    source_type = Transaction.SOURCE_CSV_IMPORT
    default_confidence = Decimal('0.900')

    def __init__(
        self,
        org,
        *,
        content: str,
        preset: str | None = None,
        column_map: dict[str, str] | None = None,
    ) -> None:
        super().__init__(org)
        self._content = content
        self._auto_detect = False
        if column_map is not None:
            self.column_map = column_map
        elif preset is not None:
            if preset not in CSV_PRESETS:
                raise ValueError(f'Unknown CSV preset: {preset!r}. Known: {", ".join(sorted(CSV_PRESETS))}.')
            self.column_map = CSV_PRESETS[preset]
        else:
            self.column_map = {}
            self._auto_detect = True

    def connect(self) -> None:
        return None

    def fetch(self) -> Iterable[Any]:
        reader = csv.DictReader(io.StringIO(self._content))
        if reader.fieldnames is None:
            raise ValueError('CSV has no header row.')

        if self._auto_detect:
            self.column_map = detect_column_map(reader.fieldnames)
            self._validate_auto_detected_map(reader.fieldnames)
        else:
            self._validate_explicit_map(reader.fieldnames)

        return list(reader)

    def _validate_auto_detected_map(self, fieldnames: list[str]) -> None:
        cm = self.column_map
        missing = [f for f in _REQUIRED_ALONE if f not in cm]
        if not any(f in cm for f in _REQUIRED_ONE_OF):
            missing.append('amount (or debit/credit)')
        if missing:
            raise ValueError(
                f'Could not automatically identify required column(s) {", ".join(missing)} '
                f'in this CSV. Found columns: {", ".join(fieldnames)}. If your file uses an '
                f'unusual layout, pass an explicit column_map or a known preset '
                f'({", ".join(sorted(CSV_PRESETS))}).'
            )

    def _validate_explicit_map(self, fieldnames: list[str]) -> None:
        missing = [
            (canonical, header) for canonical, header in self.column_map.items()
            if header not in fieldnames
        ]
        if not missing:
            return
        descriptions = ', '.join(
            f'the "{header}" column (for {canonical})' for canonical, header in missing
        )
        raise ValueError(
            f'CSV is missing {descriptions} expected by this mapping. '
            f'Found columns: {", ".join(fieldnames)}.'
        )

    def _resolve_amount(self, row: dict) -> Decimal:
        cm = self.column_map
        if 'amount' in cm:
            return _parse_decimal(row.get(cm['amount'], ''))
        # debit/credit layout: credit is an inflow (+), debit an outflow (−).
        debit = _parse_decimal(row.get(cm.get('debit', ''), '')) if 'debit' in cm else Decimal('0')
        credit = _parse_decimal(row.get(cm.get('credit', ''), '')) if 'credit' in cm else Decimal('0')
        return credit - debit

    def normalise(self, raw: dict) -> NormalizedTransaction:
        cm = self.column_map
        timestamp = _parse_date(raw.get(cm.get('date', 'date'), ''))
        amount = self._resolve_amount(raw)
        currency = (raw.get(cm.get('currency', ''), '') or self.org.base_currency).strip().upper()

        return NormalizedTransaction(
            timestamp=timestamp,
            amount=amount,
            currency=currency,
            description=raw.get(cm.get('description', ''), '').strip(),
            counterparty_name=raw.get(cm.get('counterparty', ''), '').strip(),
            merchant_name=raw.get(cm.get('merchant', ''), '').strip(),
            confidence=self.default_confidence,
            raw={'csv_row': raw},
        )
