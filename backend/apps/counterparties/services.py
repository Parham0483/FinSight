"""Counterparty resolution — turn a raw descriptor into a directory entry.

Used by the ingestion pipeline: every normalised transaction carries a
counterparty *name* (a bank descriptor, an invoice party, an accounting-API
contact). ``resolve_counterparty`` finds an existing match by canonical key or
creates an auto entry, so the directory builds itself as data arrives (§5).
"""
from __future__ import annotations

from apps.organisations.models import Organisation

from .models import Counterparty, normalise_name


def resolve_counterparty(
    org: Organisation,
    name: str,
    *,
    default_type: str = Counterparty.TYPE_OTHER,
    country_code: str = '',
) -> Counterparty | None:
    """Return an existing or newly auto-created counterparty for ``name``.

    Matching is by canonical key (``normalise_name``) within the org. A blank
    or noise-only name yields ``None`` — we don't manufacture empty parties.
    Merged entries resolve to their survivor so links never dangle.
    """
    key = normalise_name(name)
    if not key:
        return None

    existing = (
        Counterparty.objects.filter(org=org, normalised_name=key)
        .order_by('created_at')
        .first()
    )
    if existing is not None:
        # Follow a soft-merge chain to the survivor.
        while existing.merged_into_id is not None:
            existing = existing.merged_into
        return existing

    return Counterparty.objects.create(
        org=org,
        name=name.strip(),
        normalised_name=key,
        type=default_type,
        country_code=country_code,
        is_auto_created=True,
    )


def merge_counterparties(source: Counterparty, target: Counterparty) -> Counterparty:
    """Soft-merge ``source`` into ``target``, repointing its transactions.

    Non-destructive (§5.2): ``source`` is retained with ``merged_into`` set so
    the audit trail survives. Transactions are repointed to ``target``.
    """
    if source.org_id != target.org_id:
        raise ValueError('Cannot merge counterparties across organisations.')
    if source.id == target.id:
        return target

    # Repoint transactions (import locally to avoid a circular import at load).
    from apps.transactions.models import Transaction

    Transaction.objects.filter(counterparty=source).update(counterparty=target)

    # Carry over tags the survivor doesn't already have.
    merged_tags = list(dict.fromkeys([*target.tags, *source.tags]))
    target.tags = merged_tags
    target.save(update_fields=['tags', 'updated_at'])

    source.merged_into = target
    source.save(update_fields=['merged_into', 'updated_at'])
    return target
