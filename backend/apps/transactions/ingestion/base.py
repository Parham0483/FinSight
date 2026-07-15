"""The ``IngestionSource`` adapter contract and shared persistence pipeline.

Every source subclasses :class:`IngestionSource` and implements three hooks —
``connect``, ``fetch``, ``normalise`` — yielding :class:`NormalizedTransaction`
DTOs. The base ``sync`` orchestrates the rest identically for all sources:
resolve the counterparty, compute the cross-source dedup key, skip duplicates
honouring source reliability, and persist. This is the single wedge through
which all of §5's five source types enter the ledger.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable

from django.db import transaction as db_transaction

from apps.categories.models import Category
from apps.categories.services import suggest_category
from apps.counterparties.models import Counterparty
from apps.counterparties.services import resolve_counterparty
from apps.organisations.models import Organisation

from ..models import Transaction


@dataclass(frozen=True)
class NormalizedTransaction:
    """The canonical shape every source normalises a raw record into.

    Immutable by design (global coding style): a source produces these, the
    pipeline consumes them, neither mutates the other's data.
    """

    timestamp: datetime
    amount: Decimal
    currency: str
    description: str = ''
    counterparty_name: str = ''
    counterparty_type: str = Counterparty.TYPE_OTHER
    merchant_name: str = ''
    external_id: str | None = None
    confidence: Decimal = Decimal('1.000')
    category_slug: str | None = None
    country_code: str = ''
    raw: dict = field(default_factory=dict)


@dataclass
class IngestionResult:
    """Outcome of a ``sync`` run — what landed, what was skipped, what failed."""

    created: int = 0
    skipped_duplicates: int = 0
    skipped_existing: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return self.created + self.skipped_duplicates + self.skipped_existing + len(self.errors)

    def as_dict(self) -> dict:
        return {
            'created': self.created,
            'skipped_duplicates': self.skipped_duplicates,
            'skipped_existing': self.skipped_existing,
            'errors': self.errors,
            'total_processed': self.total_processed,
        }


class IngestionSource(ABC):
    """Base adapter. Subclasses supply ``connect``/``fetch``/``normalise``.

    The class attribute ``source_type`` must be one of ``Transaction.SOURCE_*``
    and stamps every record this source persists.
    """

    source_type: str = Transaction.SOURCE_MANUAL
    default_confidence: Decimal = Decimal('1.000')

    def __init__(self, org: Organisation) -> None:
        self.org = org

    # ── Hooks each source implements ──────────────────────────────────────
    @abstractmethod
    def connect(self) -> None:
        """Establish/validate access to the source. No-op for local sources."""

    @abstractmethod
    def fetch(self) -> Iterable[Any]:
        """Yield raw source records (rows, API objects, dicts…)."""

    @abstractmethod
    def normalise(self, raw: Any) -> NormalizedTransaction:
        """Map one raw record to a :class:`NormalizedTransaction`."""

    # ── Shared pipeline ───────────────────────────────────────────────────
    def sync(self) -> IngestionResult:
        """Run the full pipeline: connect → fetch → normalise → dedupe → persist."""
        result = IngestionResult()
        self.connect()

        # Cache the org's categories by slug so per-row lookup is cheap.
        category_by_slug = {c.slug: c for c in Category.objects.filter(org=self.org)}

        for raw in self.fetch():
            try:
                norm = self.normalise(raw)
            except Exception as exc:  # noqa: BLE001 — surface row errors, don't abort the batch
                result.errors.append(str(exc))
                continue
            self._persist(norm, category_by_slug, result)

        return result

    def _persist(
        self,
        norm: NormalizedTransaction,
        category_by_slug: dict[str, Category],
        result: IngestionResult,
    ) -> None:
        # 1. Idempotency: an exact (org, source, external_id) re-sync is a no-op.
        if norm.external_id:
            exists = Transaction.objects.filter(
                org=self.org, source=self.source_type, external_id=norm.external_id
            ).exists()
            if exists:
                result.skipped_existing += 1
                return

        counterparty = None
        if norm.counterparty_name:
            counterparty = resolve_counterparty(
                self.org,
                norm.counterparty_name,
                default_type=norm.counterparty_type,
                country_code=norm.country_code,
            )

        category = category_by_slug.get(norm.category_slug) if norm.category_slug else None
        if category is None:
            # Source didn't supply a category — try the rule-before-LLM ladder.
            # Never marked as `category_overridden`: that flag is reserved for
            # a human's explicit correction, not a machine guess.
            category = suggest_category(self.org, counterparty, norm.description, norm.amount)

        with db_transaction.atomic():
            txn = Transaction(
                org=self.org,
                source=self.source_type,
                external_id=norm.external_id or None,
                confidence=norm.confidence if norm.confidence is not None else self.default_confidence,
                timestamp=norm.timestamp,
                description=norm.description,
                amount=norm.amount,
                currency=norm.currency or self.org.base_currency,
                merchant_name=norm.merchant_name,
                counterparty=counterparty,
                category=category,
                raw_data=norm.raw,
            )
            # 2. Cross-source dedup: if a more (or equally) reliable record of the
            #    same movement exists, skip; if a strictly less reliable one exists,
            #    let both stand for now (reconciliation refines this later).
            dedup_hash = txn.compute_dedup_hash()
            duplicate = (
                Transaction.objects.filter(org=self.org, dedup_hash=dedup_hash)
                .exclude(dedup_hash='')
                .first()
            )
            if duplicate is not None and duplicate.source_reliability >= txn.source_reliability:
                result.skipped_duplicates += 1
                return

            txn.save()
            result.created += 1
