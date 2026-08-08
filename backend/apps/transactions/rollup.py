"""Categorised inflow/outflow rollups — where money actually comes from / goes.

The blueprint (§5) asks the dashboard to roll cash flows up by counterparty
type, tag, and category, "not just an aggregate line". This computes those
groupings as inflow/outflow/net sums in one query each.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Case, DecimalField, Q, Sum, Value, When
from django.db.models.functions import Coalesce

from .models import Transaction

_ZERO = Value(Decimal('0'), output_field=DecimalField(max_digits=18, decimal_places=2))

# Valid grouping dimensions → the ORM field/values key they roll up by.
ROLLUP_DIMENSIONS = {
    'counterparty_type': 'counterparty__type',
    'category': 'category__name',
    'counterparty': 'counterparty__name',
    'source': 'source',
}


def _inflow_outflow_aggregates() -> dict:
    inflow = Coalesce(Sum(Case(When(amount__gt=0, then='amount'), default=_ZERO)), _ZERO)
    outflow = Coalesce(Sum(Case(When(amount__lt=0, then='amount'), default=_ZERO)), _ZERO)
    return {'inflow': inflow, 'outflow': outflow, 'net': Coalesce(Sum('amount'), _ZERO)}


def rollup_by(org, dimension: str) -> list[dict]:
    """Return inflow/outflow/net per group along ``dimension`` for an org."""
    if dimension not in ROLLUP_DIMENSIONS:
        raise ValueError(
            f'Unknown rollup dimension {dimension!r}. '
            f'Choose one of: {", ".join(sorted(ROLLUP_DIMENSIONS))}.'
        )
    field = ROLLUP_DIMENSIONS[dimension]

    rows = (
        Transaction.objects.filter(org=org)
        .values(field)
        .annotate(**_inflow_outflow_aggregates())
        .order_by(field)
    )
    return [
        {
            'group': row[field] if row[field] is not None else 'uncategorised',
            'inflow': row['inflow'],
            'outflow': row['outflow'],
            'net': row['net'],
        }
        for row in rows
    ]


def rollup_by_tag(org) -> list[dict]:
    """Tags live in an ArrayField on Counterparty, so roll them up in Python.

    Each transaction contributes to every tag on its counterparty.
    """
    totals: dict[str, dict[str, Decimal]] = {}
    qs = (
        Transaction.objects.filter(org=org, counterparty__isnull=False)
        .values_list('counterparty__tags', 'amount')
    )
    for tags, amount in qs:
        for tag in (tags or []):
            bucket = totals.setdefault(tag, {'inflow': Decimal('0'), 'outflow': Decimal('0'), 'net': Decimal('0')})
            if amount >= 0:
                bucket['inflow'] += amount
            else:
                bucket['outflow'] += amount
            bucket['net'] += amount
    return [
        {'group': tag, 'inflow': b['inflow'], 'outflow': b['outflow'], 'net': b['net']}
        for tag, b in sorted(totals.items())
    ]
