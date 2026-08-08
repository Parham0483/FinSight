from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organisations.models import Organisation, OrgMembership

from .engine.combined import build_combined_daily_balance, compute_runway, summarize_drivers
from .maturity import calculate_maturity
from .serializers import CombinedForecastSerializer


class ForecastMaturityView(APIView):
    """GET /api/v1/forecast/orgs/{org_id}/maturity/ — current maturity stage for the mascot."""

    def get(self, request, org_id):
        if not OrgMembership.objects.filter(user=request.user, org_id=org_id).exists():
            return Response({'detail': 'Access denied.'}, status=403)

        profile = calculate_maturity(str(org_id))
        return Response({
            'stage': profile.stage,
            'score': profile.score,
            'component_scores': profile.component_scores,
            'days_of_data': profile.days_of_data,
            'forecast_horizon_days': profile.forecast_horizon_days,
            'progress_to_next': profile.progress_to_next,
            'mascot_message': profile.mascot_message,
            'mascot_mood': profile.mascot_mood,
            'capabilities': profile.capabilities,
            'next_milestone_days': profile.next_milestone_days,
            'next_milestone_label': profile.next_milestone_label,
        })


def _resolve_starting_balance(org: Organisation) -> Decimal:
    """Best-effort current balance: sum of connected bank accounts' own
    reported balance if any exist, else the running total of all recorded
    transaction history, else zero for a brand-new org. Not a reconciled
    "true" balance — full reconciliation against live bank data is later
    scope (§5.1), this is deliberately the simplest honest estimate Phase 2
    needs to anchor the projection.
    """
    from django.db.models import Sum

    from apps.banking.models import BankAccount
    from apps.transactions.models import Transaction

    account_total = BankAccount.objects.filter(
        connection__org=org, is_active=True, current_balance__isnull=False,
    ).aggregate(total=Sum('current_balance'))['total']
    if account_total is not None:
        return account_total

    txn_total = Transaction.objects.filter(org=org).aggregate(
        total=Sum('base_amount'),
    )['total']
    return txn_total if txn_total is not None else Decimal('0')


class CombinedForecastView(APIView):
    """GET /api/v1/forecast/orgs/{org_id}/combined/

    Layer 1 (deterministic ledger) + Layer 3 (statistical) combined daily
    balance projection, with P10/P50/P90 quantile bands, runway (most-likely
    + worst-case cash-out dates), and driver attribution — feeds the
    dashboard chart (blueprint §3, §8 Phase 2).

    Query params (all optional):
      horizon_days   int, default = the org's current maturity-stage horizon
      safety_buffer  decimal, default 0 — balance floor used for runway detection
    """

    def get(self, request, org_id):
        if not OrgMembership.objects.filter(user=request.user, org_id=org_id).exists():
            return Response({'detail': 'Access denied.'}, status=403)
        org = get_object_or_404(Organisation, id=org_id)

        horizon_days_param = request.query_params.get('horizon_days')
        if horizon_days_param is not None:
            try:
                horizon_days = int(horizon_days_param)
            except ValueError:
                return Response({'detail': '"horizon_days" must be an integer.'}, status=400)
            if horizon_days <= 0:
                return Response({'detail': '"horizon_days" must be positive.'}, status=400)
        else:
            profile = calculate_maturity(str(org_id))
            horizon_days = profile.forecast_horizon_days or 30

        safety_buffer_param = request.query_params.get('safety_buffer', '0')
        try:
            safety_buffer = Decimal(safety_buffer_param)
        except Exception:
            return Response({'detail': '"safety_buffer" must be a decimal.'}, status=400)

        starting_balance = _resolve_starting_balance(org)
        points = build_combined_daily_balance(org, horizon_days=horizon_days, starting_balance=starting_balance)
        runway = compute_runway(points, safety_buffer=safety_buffer)
        driver_totals = summarize_drivers(points)
        statistical_method = points[0].statistical_method if points else None

        payload = {
            'starting_balance': starting_balance,
            'horizon_days': horizon_days,
            'statistical_method': statistical_method,
            'points': [
                {
                    'date': p.date,
                    'known_net': p.known_net,
                    'statistical_p10': p.statistical_p10,
                    'statistical_p50': p.statistical_p50,
                    'statistical_p90': p.statistical_p90,
                    'balance_p10': p.balance_p10,
                    'balance_p50': p.balance_p50,
                    'balance_p90': p.balance_p90,
                    'drivers': p.drivers,
                }
                for p in points
            ],
            'runway': {
                'most_likely_cashout_date': runway.most_likely_cashout_date,
                'worst_case_cashout_date': runway.worst_case_cashout_date,
            },
            'driver_totals': driver_totals,
        }
        serializer = CombinedForecastSerializer(payload)
        return Response(serializer.data)
