from django.db import models

class Transaction(models.Model):
    user_id = models.IntegerField()
    
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    
    merchant = models.CharField(max_length=100, blank=True, default="")  # ADD THIS
    
    timestamp = models.DateTimeField(
        auto_now_add=True
    )
    
    idempotency_key = models.CharField(
        max_length=255,
        unique=True
    )
    
    is_fraud = models.BooleanField(
        default=False
    )
    
    fraud_score = models.FloatField(null=True, blank=True, default=0.0)
    
    rule_triggered = models.CharField(max_length=100, blank=True, default="")
    
    ml_prediction = models.JSONField(null=True, blank=True)  # ADD THIS - stores model output

    def __str__(self):
        return f"User {self.user_id} - ₹{self.amount} - {'FRAUD' if self.is_fraud else 'OK'}"
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user_id', '-timestamp']),
            models.Index(fields=['is_fraud', '-timestamp']),
        ]