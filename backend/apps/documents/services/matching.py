"""
Fuzzy matching service — links extracted document data to existing records.

After extraction, we try to find:
  - Matching Counterparty (by vendor/payee name — any type: customer, supplier, etc.)
  - Duplicate document (same amount + date + reference already exists)
  - Suggested category for transactions

NEVER auto-commits. Returns suggestions only. Human confirms.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

COUNTERPARTY_MATCH_THRESHOLD = 75   # 0–100; above this = confident match
DUPLICATE_AMOUNT_TOLERANCE = 0.01  # 1% difference = possible duplicate


@dataclass(frozen=True)
class MatchSuggestion:
    counterparty_id: Optional[str] = None
    counterparty_name: Optional[str] = None
    counterparty_match_score: float = 0.0
    is_likely_duplicate: bool = False
    duplicate_document_id: Optional[str] = None
    suggested_category: str = 'other'
    warnings: list[str] = field(default_factory=list)


def find_matches(
    org_id: str,
    extracted_data: dict,
    document_type: str,
) -> MatchSuggestion:
    """
    Given extracted document data, find matching Counterparty records
    and check for potential duplicates.
    """
    warnings: list[str] = []
    counterparty_id = None
    counterparty_name = None
    match_score = 0.0
    is_duplicate = False
    duplicate_id = None

    vendor_name = _get_vendor_name(extracted_data, document_type)
    amount = _get_amount(extracted_data)
    ref = _get_reference(extracted_data, document_type)

    # Try to match vendor/payee name to the org's counterparty directory
    if vendor_name:
        counterparty_id, counterparty_name, match_score = _match_counterparty(org_id, vendor_name)
        if match_score < COUNTERPARTY_MATCH_THRESHOLD:
            counterparty_id = None  # below threshold — don't suggest
            counterparty_name = None

    # Check for duplicate documents
    if amount and ref:
        is_duplicate, duplicate_id = _check_duplicate(org_id, amount, ref, document_type)
        if is_duplicate:
            warnings.append(
                f'Possible duplicate: a {document_type} for a similar amount '
                f'and reference was already uploaded (document ID: {duplicate_id}).'
            )

    suggested_category = _suggest_category(document_type, vendor_name or '', extracted_data)

    return MatchSuggestion(
        counterparty_id=counterparty_id,
        counterparty_name=counterparty_name,
        counterparty_match_score=match_score,
        is_likely_duplicate=is_duplicate,
        duplicate_document_id=duplicate_id,
        suggested_category=suggested_category,
        warnings=warnings,
    )


def _get_vendor_name(data: dict, document_type: str) -> str:
    if document_type == 'invoice':
        return data.get('vendor_name', '') or ''
    if document_type == 'cheque':
        return data.get('payee_name', '') or ''
    if document_type == 'purchase_order':
        return data.get('supplier_name', '') or ''
    if document_type == 'receipt':
        return data.get('merchant_name', '') or ''
    return ''


def _get_amount(data: dict) -> Optional[Decimal]:
    raw = data.get('total_amount') or data.get('amount')
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except Exception:
        return None


def _get_reference(data: dict, document_type: str) -> str:
    if document_type == 'invoice':
        return data.get('invoice_number', '') or ''
    if document_type == 'cheque':
        return data.get('cheque_number', '') or ''
    if document_type == 'purchase_order':
        return data.get('po_number', '') or ''
    return ''


def _match_counterparty(org_id: str, vendor_name: str) -> tuple[Optional[str], Optional[str], float]:
    """
    Fuzzy match vendor_name against Counterparty.name in this org, across all
    types (invoice vendors are customers, but PO/receipt/cheque parties are
    typically suppliers — restricting to one type would silently break those).
    Soft-merged entries are excluded so suggestions always point at a live
    survivor. Returns (counterparty_id, counterparty_name, score).
    """
    from apps.counterparties.models import Counterparty

    counterparties = list(
        Counterparty.objects.filter(org_id=org_id, merged_into__isnull=True)
        .values('id', 'name')
    )
    if not counterparties:
        return None, None, 0.0

    names = [c['name'] for c in counterparties]
    result = process.extractOne(
        vendor_name,
        names,
        scorer=fuzz.token_sort_ratio,
    )
    if result is None:
        return None, None, 0.0

    matched_name, score, idx = result
    counterparty_id = str(counterparties[idx]['id'])
    logger.debug('Counterparty match: "%s" → "%s" (score=%d)', vendor_name, matched_name, score)

    return counterparty_id, matched_name, float(score)


def _check_duplicate(
    org_id: str,
    amount: Decimal,
    reference: str,
    document_type: str,
) -> tuple[bool, Optional[str]]:
    """
    Check if a document with same reference and similar amount already exists.
    """
    from apps.documents.models import Document

    # Find documents with matching reference (exact) or very similar amount
    existing = Document.objects.filter(
        org_id=org_id,
        document_type=document_type,
        status__in=['review', 'confirmed'],
    ).exclude(confirmed_data=None)

    for doc in existing:
        confirmed = doc.confirmed_data or {}
        existing_ref = _get_reference(confirmed, document_type)
        existing_amount = _get_amount(confirmed)

        if reference and existing_ref and reference.strip() == existing_ref.strip():
            logger.info('Duplicate detected by reference: %s', reference)
            return True, str(doc.id)

        if amount and existing_amount:
            diff = abs(amount - existing_amount) / max(amount, existing_amount)
            if diff <= DUPLICATE_AMOUNT_TOLERANCE:
                logger.debug('Possible duplicate by amount: %s ≈ %s', amount, existing_amount)
                return True, str(doc.id)

    return False, None


def _suggest_category(document_type: str, vendor_name: str, data: dict) -> str:
    """Heuristic category suggestion based on document type and vendor keywords."""
    name_lower = vendor_name.lower()

    if document_type in ('invoice', 'purchase_order'):
        payroll_keywords = ('salary', 'payroll', 'wages', 'staff', 'employee')
        rent_keywords = ('rent', 'lease', 'property', 'landlord', 'warehouse')
        tax_keywords = ('hmrc', 'vat', 'tax', 'customs', 'duty', 'border force')
        bank_keywords = ('bank', 'barclays', 'hsbc', 'lloyds', 'natwest', 'monzo', 'revolut')

        for kw in payroll_keywords:
            if kw in name_lower:
                return 'payroll'
        for kw in rent_keywords:
            if kw in name_lower:
                return 'rent_overhead'
        for kw in tax_keywords:
            if kw in name_lower:
                return 'tax'
        for kw in bank_keywords:
            if kw in name_lower:
                return 'bank_fee'
        return 'supplier_payment'

    if document_type == 'receipt':
        return 'rent_overhead'

    if document_type == 'cheque':
        return 'supplier_payment'

    if document_type == 'bank_statement':
        return 'other'

    return 'other'
