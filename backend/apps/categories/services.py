"""Auto-categorisation: rule-check-before-LLM, per the correction ladder
(blueprint §5.2 / money-handling invariant 3 — rule promotion is preferred
over any fancier mechanism, checked first, always).

Ladder, in order:
  1. Learned rule (CategorisationRule, promoted after 2 reinforcing corrections)
  2. Deterministic keyword heuristic (free, no API call)
  3. LLM classification (Claude Haiku) — only when ANTHROPIC_API_KEY is
     configured; only ever returns a slug that exists in the org's own
     taxonomy, never invents one
  4. None — left uncategorised for a human to assign, rather than guessing
     without any signal

Never auto-commits a *correction* — this module only suggests at ingest.
Corrections themselves come from a human editing `Transaction.category`
(see `TransactionDetailView.patch`), which calls `record_correction` here.
"""
from __future__ import annotations

import logging

from anthropic import Anthropic
from django.conf import settings

from apps.counterparties.models import Counterparty

from .models import Category, CategorisationRule

logger = logging.getLogger(__name__)

HAIKU_MODEL = 'claude-haiku-4-5-20251001'

# (slug, keywords) — checked in order, first match wins. Mirrors the heuristic
# in documents/services/matching.py but keyed to transaction descriptions
# rather than document vendor names, so kept separate rather than shared.
_EXPENSE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ('payroll', ('salary', 'payroll', 'wages', 'staff pay')),
    ('rent_overhead', ('rent', 'lease', 'property mgmt', 'landlord')),
    ('tax', ('hmrc', 'vat', 'corporation tax', 'paye', 'customs', 'duty')),
    ('bank_fee', ('bank fee', 'overdraft fee', 'card fee', 'account fee')),
    ('loan_repayment', ('loan repayment', 'loan installment', 'finance repayment')),
]

_INCOME_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ('interest_income', ('interest received', 'interest credit')),
    ('refund_received', ('refund', 'reversal', 'chargeback credit')),
]


def suggest_category(
    org,
    counterparty: Counterparty | None,
    description: str,
    amount,
) -> Category | None:
    """Return the best-guess Category for a transaction, or None.

    `amount` follows the existing sign convention (positive = inflow), same
    as `Transaction.direction`.
    """
    rule_category = _check_rule(org, counterparty)
    if rule_category is not None:
        return rule_category

    keyword_category = _check_keywords(org, description, amount)
    if keyword_category is not None:
        return keyword_category

    return _check_llm(org, counterparty, description, amount)


def record_correction(org, counterparty: Counterparty | None, category: Category) -> None:
    """A human corrected (or explicitly set) a transaction's category.

    Reinforces the counterparty's rule if it agrees with the correction, or
    resets it if the correction contradicts an existing rule — the most
    recent human judgement wins, it never averages toward a stale answer.
    No-op without a counterparty: there's no stable key to attach a rule to.
    """
    if counterparty is None:
        return

    rule, created = CategorisationRule.objects.get_or_create(
        org=org, counterparty=counterparty,
        defaults={'category': category, 'hit_count': 1},
    )
    if created:
        return

    if rule.category_id == category.id:
        rule.hit_count += 1
    else:
        rule.category = category
        rule.hit_count = 1
    rule.save(update_fields=['category', 'hit_count', 'updated_at'])


def _check_rule(org, counterparty: Counterparty | None) -> Category | None:
    if counterparty is None:
        return None
    rule = (
        CategorisationRule.objects.filter(
            org=org, counterparty=counterparty, hit_count__gte=CategorisationRule.PROMOTION_THRESHOLD,
        )
        .select_related('category')
        .first()
    )
    return rule.category if rule else None


def _check_keywords(org, description: str, amount) -> Category | None:
    text = (description or '').lower()
    keyword_table = _INCOME_KEYWORDS if amount and amount > 0 else _EXPENSE_KEYWORDS
    for slug, keywords in keyword_table:
        if any(kw in text for kw in keywords):
            return Category.objects.filter(org=org, slug=slug).first()
    return None


def _check_llm(org, counterparty: Counterparty | None, description: str, amount) -> Category | None:
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not api_key:
        return None  # no key configured — leave uncategorised rather than guess blind

    taxonomy = list(Category.objects.filter(org=org).values_list('slug', 'name'))
    if not taxonomy:
        return None

    try:
        client = Anthropic(api_key=api_key)
        slug_options = ', '.join(slug for slug, _ in taxonomy)
        direction = 'inflow (money received)' if amount and amount > 0 else 'outflow (money paid out)'
        prompt = (
            f'Transaction: "{description}" from/to "{counterparty.name if counterparty else "unknown"}", '
            f'a {direction}.\n'
            f'Pick exactly one category slug from this list, or "none" if nothing fits: {slug_options}.\n'
            f'Respond with only the slug, nothing else.'
        )
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=16,
            messages=[{'role': 'user', 'content': prompt}],
        )
        suggested_slug = response.content[0].text.strip().lower()
    except Exception:
        logger.exception('LLM categorisation call failed; leaving transaction uncategorised')
        return None

    valid_slugs = {slug for slug, _ in taxonomy}
    if suggested_slug not in valid_slugs:
        return None  # never invent a category outside the org's own taxonomy

    return Category.objects.filter(org=org, slug=suggested_slug).first()
