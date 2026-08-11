from django.contrib import admin
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'user_id', 
        'amount', 
        'merchant',
        'is_fraud', 
        'fraud_score', 
        'rule_triggered', 
        'timestamp'
    ]
    
    list_filter = [
        'is_fraud', 
        'rule_triggered',
        'timestamp',
        'merchant',
    ]
    
    search_fields = [
        'user_id', 
        'idempotency_key', 
        'merchant',
        'id',
    ]
    
    ordering = ['-timestamp']
    
    readonly_fields = [
        'id',
        'timestamp', 
        'fraud_score',
        'is_fraud',
        'rule_triggered',
        'ml_prediction',
    ]
    
    list_per_page = 50
    
    # Color code fraud vs legit
    def get_list_display(self, request):
        return self.list_display
    
    def is_fraud(self, obj):
        return obj.is_fraud
    is_fraud.boolean = True  # Shows as red/green icon
    is_fraud.short_description = 'Fraud?'
    
    # Show fraud_score with 2 decimals
    def fraud_score(self, obj):
        if obj.fraud_score is not None:
            return f"{obj.fraud_score:.2f}"
        return "-"
    fraud_score.admin_order_field = 'fraud_score'
    
    # Add date hierarchy for filtering by day/month/year
    date_hierarchy = 'timestamp'
    
    # Make amount look like money
    def amount(self, obj):
        return f"₹{obj.amount:,.2f}"
    amount.admin_order_field = 'amount'