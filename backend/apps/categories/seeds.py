"""Default transaction-category taxonomy and per-org seeding.

The taxonomy is intentionally small and universal; orgs extend it with their
own custom categories. Each entry is ``(slug, name, [children])`` grouped
under a top-level kind. Children inherit their parent's kind.
"""
from apps.organisations.models import Organisation

from .models import Category

# (kind, root_slug, root_name, [(child_slug, child_name), ...])
DEFAULT_TAXONOMY: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    (Category.KIND_INCOME, 'income', 'Income', [
        ('customer_receipt', 'Customer Receipt'),
        ('refund_received', 'Refund Received'),
        ('interest_income', 'Interest Income'),
        ('other_income', 'Other Income'),
    ]),
    (Category.KIND_EXPENSE, 'expenses', 'Expenses', [
        ('supplier_payment', 'Supplier Payment'),
        ('payroll', 'Payroll'),
        ('rent_overhead', 'Rent / Overhead'),
        ('tax', 'Tax'),
        ('loan_repayment', 'Loan Repayment'),
        ('bank_fee', 'Bank Fee'),
        ('other_expense', 'Other Expense'),
    ]),
    (Category.KIND_TRANSFER, 'transfers', 'Transfers', [
        ('fx_transfer', 'FX Transfer'),
        ('internal_transfer', 'Internal Transfer'),
    ]),
]


def seed_default_categories(org: Organisation) -> int:
    """Idempotently create the default taxonomy for ``org``.

    Returns the number of categories created (0 if everything already exists).
    """
    created = 0
    for kind, root_slug, root_name, children in DEFAULT_TAXONOMY:
        root, was_created = Category.objects.get_or_create(
            org=org, slug=root_slug,
            defaults={'name': root_name, 'kind': kind, 'is_system': True, 'parent': None},
        )
        created += int(was_created)
        for child_slug, child_name in children:
            _, child_created = Category.objects.get_or_create(
                org=org, slug=child_slug,
                defaults={'name': child_name, 'kind': kind, 'is_system': True, 'parent': root},
            )
            created += int(child_created)
    return created
