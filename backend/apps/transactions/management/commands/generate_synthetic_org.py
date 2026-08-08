"""Generate a realistic synthetic organisation for demos and backtest fixtures.

The blueprint (§5) calls for a synthetic-org generator producing realistic
seasonal SME patterns. This command builds a fully populated org: default
categories, a counterparty directory (customers, suppliers, an employee, a
landlord, the tax authority), and a daily transaction stream with recurring
obligations (rent, payroll, tax), seasonal revenue, and per-customer late
payment behaviour — the exact texture the forecasting engine later needs.

Deterministic given ``--seed`` so backtest fixtures are reproducible.

Usage:
    python manage.py generate_synthetic_org --profile cafe --days 365 --seed 42
"""
from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.categories.models import Category
from apps.categories.seeds import seed_default_categories
from apps.counterparties.models import Counterparty
from apps.organisations.models import Organisation
from apps.transactions.models import Transaction

# Per-profile shape: base daily revenue, seasonal amplitude (0–1), a monthly
# seasonal multiplier curve (index 0 = January), and supplier cost ratio.
PROFILES: dict[str, dict] = {
    'cafe': {
        'name': 'Corner Café',
        'industry': 'hospitality',
        'currency': 'GBP',
        'country': 'GB',
        'daily_revenue': Decimal('420'),
        'revenue_jitter': Decimal('0.35'),
        # Cafés peak in summer, dip in deep winter.
        'monthly_curve': [0.8, 0.8, 0.95, 1.0, 1.1, 1.2, 1.25, 1.2, 1.05, 0.95, 0.85, 1.0],
        'cost_ratio': Decimal('0.45'),
        'rent': Decimal('2200'),
        'payroll': Decimal('5400'),
        'customers': ['Office Catering Co', 'Weekend Market Stall', 'Local Deliveroo', 'Walk-in Sales'],
        'suppliers': ['Beanwholesale Ltd', 'Dairy Direct', 'FreshProduce Co', 'Bakery Supplies UK'],
    },
    'agency': {
        'name': 'Northstar Digital Agency',
        'industry': 'professional_services',
        'currency': 'GBP',
        'country': 'GB',
        'daily_revenue': Decimal('1100'),
        'revenue_jitter': Decimal('0.5'),
        # Agencies dip over summer holidays and December.
        'monthly_curve': [1.1, 1.15, 1.2, 1.1, 1.0, 0.9, 0.8, 0.75, 1.05, 1.2, 1.2, 0.85],
        'cost_ratio': Decimal('0.25'),
        'rent': Decimal('3500'),
        'payroll': Decimal('22000'),
        'customers': ['Acme Retail', 'Globex Corp', 'Initech Software', 'Umbrella Brands', 'Soylent Foods'],
        'suppliers': ['AWS', 'Adobe Creative Cloud', 'Freelance Pool', 'WeWork Offices'],
    },
    'ecommerce': {
        'name': 'Driftwood Goods',
        'industry': 'retail',
        'currency': 'USD',
        'country': 'US',
        'daily_revenue': Decimal('1800'),
        'revenue_jitter': Decimal('0.45'),
        # E-commerce spikes hard into Q4 (holiday shopping).
        'monthly_curve': [0.85, 0.8, 0.9, 0.95, 1.0, 1.0, 0.95, 1.0, 1.1, 1.3, 1.7, 1.9],
        'cost_ratio': Decimal('0.55'),
        'rent': Decimal('1800'),
        'payroll': Decimal('14000'),
        'customers': ['Amazon Marketplace', 'Shopify Storefront', 'Etsy Channel', 'Wholesale B2B'],
        'suppliers': ['Shenzhen Manufacturing', 'PrintLabel Co', 'ShipFast Logistics', 'Packaging Plus'],
    },
    # A genuinely early-stage org, not just artificially sparse test data: a solo
    # consultant a couple of months in, who logs transactions in occasional batches
    # rather than daily and has been behind on bookkeeping for the last month —
    # a realistic, common pattern for a brand-new one-person business, not an
    # abandoned one. Uses a dedicated generation path (`learning_preset`) instead
    # of the daily seasonal-revenue model the other profiles use, because that
    # model's very act of transacting every day makes calculate_maturity's
    # coverage-density + reconciliation-exemption + recency components float the
    # score into 'developing' within the first week or two regardless of how few
    # total days are requested — confirmed empirically, not assumed. The
    # transaction count (4) and window (34 active days + 32 quiet days) below are
    # calibration constants tuned against the real calculate_maturity formula to
    # land reliably in the 'learning' bucket (score ~20-22 of the 5-25 range, with
    # margin) — they are not meant to scale with --days, which this profile ignores.
    'solo_trader': {
        'name': 'Fresh Start Consulting',
        'industry': 'professional_services',
        'currency': 'GBP',
        'country': 'GB',
        'learning_preset': True,
        'customers': ['First Referral Client', 'Word-of-Mouth Customer'],
        'suppliers': ['Accounting Software Subscription'],
    },
}

# Calibration constants for the 'solo_trader' learning_preset — see PROFILES comment above.
_LEARNING_PRESET_TRANSACTION_COUNT = 4
_LEARNING_PRESET_ACTIVE_SPAN_DAYS = 34
_LEARNING_PRESET_QUIET_GAP_DAYS = 32

_TWO_DP = Decimal('0.01')


def _money(value: Decimal) -> Decimal:
    return value.quantize(_TWO_DP, rounding=ROUND_HALF_UP)


class Command(BaseCommand):
    help = 'Generate a synthetic organisation with realistic seasonal SME cash flows.'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--profile', choices=sorted(PROFILES), default='cafe')
        parser.add_argument('--days', type=int, default=365, help='Days of history to generate.')
        parser.add_argument('--seed', type=int, default=None, help='RNG seed for reproducibility.')
        parser.add_argument('--name', type=str, default=None, help='Override the org name.')

    def handle(self, *args, **options) -> None:
        profile_key = options['profile']
        days = options['days']
        if days < 1:
            raise CommandError('--days must be >= 1.')
        rng = random.Random(options['seed'])
        profile = PROFILES[profile_key]

        with db_transaction.atomic():
            org = self._create_org(profile, options.get('name'))
            seed_default_categories(org)
            categories = {c.slug: c for c in Category.objects.filter(org=org)}
            customers, suppliers, employee, landlord, tax_authority = self._create_counterparties(org, profile)

            if profile.get('learning_preset'):
                created = self._generate_learning_preset_transactions(
                    org, rng, customers, suppliers,
                )
            else:
                created = self._generate_transactions(
                    org, profile, days, rng, categories,
                    customers, suppliers, employee, landlord, tax_authority,
                )

        if profile.get('learning_preset'):
            span_note = (
                f'{_LEARNING_PRESET_ACTIVE_SPAN_DAYS + _LEARNING_PRESET_QUIET_GAP_DAYS} days '
                f'(fixed calibration window — --days is ignored for this profile)'
            )
        else:
            span_note = f'{days} days'
        self.stdout.write(self.style.SUCCESS(
            f'Created synthetic org "{org.name}" ({org.id}) with {created} transactions '
            f'over {span_note} [profile={profile_key}].'
        ))

    def _create_org(self, profile: dict, name_override: str | None) -> Organisation:
        return Organisation.objects.create(
            name=name_override or profile['name'],
            industry=profile['industry'],
            country_code=profile['country'],
            base_currency=profile['currency'],
            is_demo=True,
        )

    def _create_counterparties(self, org: Organisation, profile: dict):
        customers = [
            Counterparty.objects.create(
                org=org, name=n, type=Counterparty.TYPE_CUSTOMER,
                country_code=profile['country'], is_auto_created=False,
            )
            for n in profile['customers']
        ]
        suppliers = [
            Counterparty.objects.create(
                org=org, name=n, type=Counterparty.TYPE_SUPPLIER,
                country_code=profile['country'], is_auto_created=False,
            )
            for n in profile['suppliers']
        ]
        employee = Counterparty.objects.create(
            org=org, name='Payroll Run', type=Counterparty.TYPE_EMPLOYEE, is_auto_created=False,
        )
        landlord = Counterparty.objects.create(
            org=org, name='Property Holdings Ltd', type=Counterparty.TYPE_SUPPLIER, is_auto_created=False,
        )
        tax_authority = Counterparty.objects.create(
            org=org, name='Tax Authority', type=Counterparty.TYPE_TAX_AUTHORITY, is_auto_created=False,
        )
        return customers, suppliers, employee, landlord, tax_authority

    def _generate_transactions(  # noqa: PLR0913 — synthetic generator wires many parts
        self, org, profile, days, rng, categories,
        customers, suppliers, employee, landlord, tax_authority,
    ) -> int:
        currency = profile['currency']
        start = (timezone.now() - timedelta(days=days - 1)).replace(hour=10, minute=0, second=0, microsecond=0)
        batch: list[Transaction] = []

        receipt_cat = categories.get('customer_receipt')
        supplier_cat = categories.get('supplier_payment')
        payroll_cat = categories.get('payroll')
        rent_cat = categories.get('rent_overhead')
        tax_cat = categories.get('tax')

        for day_offset in range(days):
            day = start + timedelta(days=day_offset)
            month_mult = Decimal(str(profile['monthly_curve'][day.month - 1]))

            # ── Daily revenue (customer receipts), seasonal + jittered ──────
            jitter = Decimal(str(rng.uniform(
                float(1 - profile['revenue_jitter']), float(1 + profile['revenue_jitter'])
            )))
            # Weekends: cafés/ecommerce busier, agencies quiet.
            weekday = day.weekday()
            weekend_factor = Decimal('1.2') if weekday >= 5 and profile['industry'] != 'professional_services' else Decimal('1.0')
            if weekday >= 5 and profile['industry'] == 'professional_services':
                weekend_factor = Decimal('0.2')

            revenue = _money(profile['daily_revenue'] * month_mult * jitter * weekend_factor)
            if revenue > 0:
                customer = rng.choice(customers)
                batch.append(self._txn(
                    org, currency, day, revenue, receipt_cat, customer,
                    f'Sales — {customer.name}', Transaction.SOURCE_MANUAL,
                ))

            # ── Supplier costs roughly tracking revenue, every couple of days ─
            if day_offset % 2 == 0:
                supplier = rng.choice(suppliers)
                cost = _money(revenue * profile['cost_ratio'] * Decimal(str(rng.uniform(0.8, 1.4))))
                if cost > 0:
                    batch.append(self._txn(
                        org, currency, day, -cost, supplier_cat, supplier,
                        f'Supplier — {supplier.name}', Transaction.SOURCE_MANUAL,
                    ))

            # ── Monthly rent (1st), payroll (28th), quarterly tax ───────────
            if day.day == 1:
                batch.append(self._txn(
                    org, currency, day, -_money(profile['rent']), rent_cat, landlord,
                    'Monthly rent', Transaction.SOURCE_MANUAL,
                ))
            if day.day == 28:
                batch.append(self._txn(
                    org, currency, day, -_money(profile['payroll']), payroll_cat, employee,
                    'Payroll run', Transaction.SOURCE_MANUAL,
                ))
            if day.day == 7 and day.month in (1, 4, 7, 10):
                tax_amount = _money(profile['payroll'] * Decimal('0.3'))
                batch.append(self._txn(
                    org, currency, day, -tax_amount, tax_cat, tax_authority,
                    'Quarterly tax payment', Transaction.SOURCE_MANUAL,
                ))

        # Persisting one-by-one runs the save() hook (dedup hash); fine for fixtures.
        for txn in batch:
            txn.save()
        return len(batch)

    def _generate_learning_preset_transactions(
        self, org, rng, customers, suppliers,
    ) -> int:
        """See the 'solo_trader' PROFILES entry for why this is a separate, deliberately
        sparse generation path rather than a low-volume pass through the daily model.

        Deliberately uncategorised (category=None): calculate_maturity's categorisation_rate
        component alone contributes 15 of the 100 score points at 100% categorised, which —
        combined with the fixed source_reliability/reconciliation floor every manual-only,
        no-invoice org gets — already exceeds the 'learning' stage's score ceiling (25) on
        its own. A brand-new user who hasn't gotten around to categorising every transaction
        yet is realistic, not a workaround; confirmed this is what actually keeps the
        calibration in the 'learning' bucket, not just an assumption.
        """
        currency = 'GBP'

        span = _LEARNING_PRESET_ACTIVE_SPAN_DAYS
        count = _LEARNING_PRESET_TRANSACTION_COUNT
        gap = _LEARNING_PRESET_QUIET_GAP_DAYS
        offsets = [round(i * (span - 1) / (count - 1)) for i in range(count)]

        batch: list[Transaction] = []
        for i, offset in enumerate(offsets):
            days_ago = gap + (span - 1 - offset)
            timestamp = (timezone.now() - timedelta(days=days_ago)).replace(
                hour=14, minute=0, second=0, microsecond=0,
            )
            if i % 2 == 0:
                customer = rng.choice(customers)
                amount = _money(Decimal(str(rng.uniform(150, 400))))
                batch.append(self._txn(
                    org, currency, timestamp, amount, None, customer,
                    f'Client payment — {customer.name}', Transaction.SOURCE_MANUAL,
                ))
            else:
                supplier = rng.choice(suppliers)
                amount = -_money(Decimal(str(rng.uniform(20, 60))))
                batch.append(self._txn(
                    org, currency, timestamp, amount, None, supplier,
                    f'Supplier — {supplier.name}', Transaction.SOURCE_MANUAL,
                ))

        for txn in batch:
            txn.save()
        return len(batch)

    def _txn(self, org, currency, timestamp, amount, category, counterparty, description, source) -> Transaction:
        return Transaction(
            org=org,
            source=source,
            timestamp=timestamp,
            amount=amount,
            currency=currency,
            base_currency=currency,
            base_amount=amount,
            fx_rate=Decimal('1.0'),
            description=description,
            category=category,
            counterparty=counterparty,
            confidence=Decimal('1.000'),
        )
