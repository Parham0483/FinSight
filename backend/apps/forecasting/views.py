from rest_framework.response import Response
from rest_framework.views import APIView
from apps.organisations.models import OrgMembership
from .maturity import calculate_maturity


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
