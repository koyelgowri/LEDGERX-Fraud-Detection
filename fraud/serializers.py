from rest_framework import serializers
from .models import Transaction
from decimal import Decimal

class TransactionSerializer(serializers.ModelSerializer):
    # Make amount return as float instead of string for easier frontend use
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=False)
    
    class Meta:
        model = Transaction
        fields = [
            "id",
            "user_id",
            "amount",
            "merchant",              # ADD - API needs to accept this
            "timestamp",
            "idempotency_key",
            "is_fraud",
            "fraud_score",           # ADD - Return ML score
            "rule_triggered",        # ADD - Return why it flagged
            "ml_prediction",         # ADD - Return full ML details
        ]
        read_only_fields = [
            "id",
            "timestamp",
            "is_fraud",              # ML decides this, not user
            "fraud_score",           # ML decides this
            "rule_triggered",        # ML decides this
            "ml_prediction",         # ML decides this
        ]
    
    def validate_amount(self, value):
        """Reject negative amounts"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        if value > Decimal('9999999999.99'):
            raise serializers.ValidationError("Amount too large")
        return value
    
    def validate_idempotency_key(self, value):
        """Ensure idempotency_key is unique"""
        if Transaction.objects.filter(idempotency_key=value).exists():
            raise serializers.ValidationError("Transaction with this idempotency_key already exists")
        return value


# Separate serializer for list view - hide heavy ml_prediction JSON
class TransactionListSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=False)
    
    class Meta:
        model = Transaction
        fields = [
            "id",
            "user_id", 
            "amount",
            "merchant",
            "timestamp",
            "is_fraud",
            "fraud_score",
            "rule_triggered",
            # ml_prediction excluded = faster list API
        ]