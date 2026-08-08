from rest_framework import serializers


class DailyBalancePointSerializer(serializers.Serializer):
    """Mirrors `engine.combined.DailyBalancePoint` — one day of the combined
    Layer 1 (known) + Layer 3 (statistical) projected balance.
    """
    date = serializers.DateField()
    known_net = serializers.DecimalField(max_digits=15, decimal_places=2)
    statistical_p10 = serializers.DecimalField(max_digits=15, decimal_places=2)
    statistical_p50 = serializers.DecimalField(max_digits=15, decimal_places=2)
    statistical_p90 = serializers.DecimalField(max_digits=15, decimal_places=2)
    balance_p10 = serializers.DecimalField(max_digits=15, decimal_places=2)
    balance_p50 = serializers.DecimalField(max_digits=15, decimal_places=2)
    balance_p90 = serializers.DecimalField(max_digits=15, decimal_places=2)
    drivers = serializers.DictField(child=serializers.DecimalField(max_digits=15, decimal_places=2))


class RunwaySerializer(serializers.Serializer):
    most_likely_cashout_date = serializers.DateField(allow_null=True)
    worst_case_cashout_date = serializers.DateField(allow_null=True)


class CombinedForecastSerializer(serializers.Serializer):
    starting_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    horizon_days = serializers.IntegerField()
    statistical_method = serializers.CharField(allow_null=True)
    points = DailyBalancePointSerializer(many=True)
    runway = RunwaySerializer()
    driver_totals = serializers.DictField(child=serializers.DecimalField(max_digits=15, decimal_places=2))
