"""Auto-categorisation ladder: rule (promoted) -> keyword -> LLM -> None.
Risk-based per the money-handling skill's correction-ladder mandate.
"""
from unittest.mock import MagicMock, patch

import pytest

from apps.categories.models import Category, CategorisationRule
from apps.categories.seeds import seed_default_categories
from apps.categories.services import record_correction, suggest_category
from apps.counterparties.models import Counterparty

pytestmark = pytest.mark.unit


@pytest.fixture
def seeded_org(org):
    seed_default_categories(org)
    return org


@pytest.mark.django_db
def test_promoted_rule_wins_over_keyword_match(seeded_org):
    supplier = Counterparty.objects.create(org=seeded_org, name='Beanwholesale Ltd', type=Counterparty.TYPE_SUPPLIER)
    payroll = Category.objects.get(org=seeded_org, slug='payroll')
    CategorisationRule.objects.create(org=seeded_org, counterparty=supplier, category=payroll, hit_count=2)

    # Description would keyword-match 'rent_overhead', but the promoted rule wins.
    result = suggest_category(seeded_org, supplier, 'monthly rent for warehouse', -100)

    assert result == payroll


@pytest.mark.django_db
def test_unpromoted_rule_is_not_used(seeded_org):
    supplier = Counterparty.objects.create(org=seeded_org, name='Beanwholesale Ltd', type=Counterparty.TYPE_SUPPLIER)
    payroll = Category.objects.get(org=seeded_org, slug='payroll')
    CategorisationRule.objects.create(org=seeded_org, counterparty=supplier, category=payroll, hit_count=1)

    # hit_count=1 is below PROMOTION_THRESHOLD=2, so it falls through to keywords.
    result = suggest_category(seeded_org, supplier, 'rent for warehouse', -100)

    assert result == Category.objects.get(org=seeded_org, slug='rent_overhead')


@pytest.mark.django_db
def test_keyword_heuristic_matches_expense(seeded_org):
    result = suggest_category(seeded_org, None, 'HMRC VAT payment', -500)
    assert result == Category.objects.get(org=seeded_org, slug='tax')


@pytest.mark.django_db
def test_keyword_heuristic_matches_income(seeded_org):
    result = suggest_category(seeded_org, None, 'Interest received on savings', 12)
    assert result == Category.objects.get(org=seeded_org, slug='interest_income')


@pytest.mark.django_db
def test_no_signal_returns_none_without_llm_key(seeded_org, settings):
    settings.ANTHROPIC_API_KEY = ''
    result = suggest_category(seeded_org, None, 'totally ambiguous description', -10)
    assert result is None


@pytest.mark.django_db
def test_llm_fallback_used_when_no_rule_or_keyword_match(seeded_org, settings):
    settings.ANTHROPIC_API_KEY = 'test-key'

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='bank_fee')]

    with patch('apps.categories.services.Anthropic') as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = mock_response
        result = suggest_category(seeded_org, None, 'unusual charge XZ29', -5)

    assert result == Category.objects.get(org=seeded_org, slug='bank_fee')


@pytest.mark.django_db
def test_llm_never_invents_a_slug_outside_taxonomy(seeded_org, settings):
    settings.ANTHROPIC_API_KEY = 'test-key'

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='not_a_real_slug')]

    with patch('apps.categories.services.Anthropic') as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = mock_response
        result = suggest_category(seeded_org, None, 'unusual charge', -5)

    assert result is None


@pytest.mark.django_db
def test_llm_failure_leaves_transaction_uncategorised(seeded_org, settings):
    settings.ANTHROPIC_API_KEY = 'test-key'

    with patch('apps.categories.services.Anthropic') as MockAnthropic:
        MockAnthropic.return_value.messages.create.side_effect = RuntimeError('network error')
        result = suggest_category(seeded_org, None, 'unusual charge', -5)

    assert result is None


@pytest.mark.django_db
def test_record_correction_promotes_after_two_matching_corrections(seeded_org):
    supplier = Counterparty.objects.create(org=seeded_org, name='Dairy Direct', type=Counterparty.TYPE_SUPPLIER)
    supplier_payment = Category.objects.get(org=seeded_org, slug='supplier_payment')

    record_correction(seeded_org, supplier, supplier_payment)
    rule = CategorisationRule.objects.get(org=seeded_org, counterparty=supplier)
    assert rule.hit_count == 1
    assert not rule.is_promoted

    record_correction(seeded_org, supplier, supplier_payment)
    rule.refresh_from_db()
    assert rule.hit_count == 2
    assert rule.is_promoted


@pytest.mark.django_db
def test_record_correction_contradicting_previous_resets_counter(seeded_org):
    supplier = Counterparty.objects.create(org=seeded_org, name='Dairy Direct', type=Counterparty.TYPE_SUPPLIER)
    supplier_payment = Category.objects.get(org=seeded_org, slug='supplier_payment')
    rent = Category.objects.get(org=seeded_org, slug='rent_overhead')

    record_correction(seeded_org, supplier, supplier_payment)
    record_correction(seeded_org, supplier, supplier_payment)  # promoted at hit_count=2

    record_correction(seeded_org, supplier, rent)  # human corrects again, differently

    rule = CategorisationRule.objects.get(org=seeded_org, counterparty=supplier)
    assert rule.category == rent
    assert rule.hit_count == 1
    assert not rule.is_promoted


@pytest.mark.django_db
def test_record_correction_without_counterparty_is_a_noop(seeded_org):
    category = Category.objects.get(org=seeded_org, slug='other_expense')
    record_correction(seeded_org, None, category)
    assert CategorisationRule.objects.count() == 0
