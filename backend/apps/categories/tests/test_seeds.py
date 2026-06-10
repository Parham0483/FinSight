import pytest

from apps.categories.models import Category
from apps.categories.seeds import DEFAULT_TAXONOMY, seed_default_categories

pytestmark = pytest.mark.integration


def test_seed_creates_hierarchical_taxonomy(org):
    created = seed_default_categories(org)

    assert created > 0
    # Every default top-level group and its children exist.
    roots = Category.objects.filter(org=org, parent__isnull=True)
    assert roots.count() == len(DEFAULT_TAXONOMY)
    # All seeded rows are flagged as system categories.
    assert Category.objects.filter(org=org).count() == Category.objects.filter(org=org, is_system=True).count()


def test_seed_is_idempotent(org):
    first = seed_default_categories(org)
    total_after_first = Category.objects.filter(org=org).count()

    second = seed_default_categories(org)

    assert first == total_after_first
    assert second == 0  # nothing new created on the second run
    assert Category.objects.filter(org=org).count() == total_after_first


def test_children_link_to_parent_and_inherit_kind(org):
    seed_default_categories(org)
    expense_root = Category.objects.get(org=org, slug='expenses', parent__isnull=True)
    children = Category.objects.filter(parent=expense_root)

    assert children.exists()
    assert all(c.kind == Category.KIND_EXPENSE for c in children)


def test_full_path_walks_ancestors(org):
    seed_default_categories(org)
    child = Category.objects.filter(org=org, parent__isnull=False).first()

    assert child.full_path == f'{child.parent.name} / {child.name}'


def test_categories_are_scoped_per_org(org, db):
    from apps.organisations.models import Organisation

    other = Organisation.objects.create(name='Other Co', base_currency='USD')
    seed_default_categories(org)
    seed_default_categories(other)

    org_slugs = set(Category.objects.filter(org=org).values_list('slug', flat=True))
    other_slugs = set(Category.objects.filter(org=other).values_list('slug', flat=True))
    assert org_slugs == other_slugs  # same taxonomy
    # but distinct rows
    assert not Category.objects.filter(org=org).filter(
        id__in=Category.objects.filter(org=other).values('id')
    ).exists()
