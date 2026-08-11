from rest_framework import viewsets, status
from rest_framework.response import Response
from.kafka_producer import send_transaction_event
from rest_framework.pagination import PageNumberPagination
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from.models import Transaction
from.serializers import TransactionSerializer, TransactionListSerializer
import uuid
import logging

logger = logging.getLogger(__name__)

class TransactionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

@method_decorator(never_cache, name='dispatch')
class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all().order_by('-timestamp')
    pagination_class = TransactionPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return TransactionListSerializer
        return TransactionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Latest filter
        latest = self.request.query_params.get('latest')
        if latest == 'true':
            queryset = queryset[:1]

        # Existing filters
        is_fraud = self.request.query_params.get('is_fraud')
        user_id = self.request.query_params.get('user_id')

        if is_fraud is not None:
            queryset = queryset.filter(is_fraud=is_fraud.lower() == 'true')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if 'idempotency_key' not in serializer.validated_data:
            serializer.validated_data['idempotency_key'] = str(uuid.uuid4())

        transaction = serializer.save(
            is_fraud=False,
            fraud_score=None,
            rule_triggered="pending",
            ml_prediction={"status": "pending_processing"}
        )

        try:
            kafka_data = TransactionSerializer(transaction).data
            kafka_data['amount'] = str(kafka_data['amount'])
            kafka_data['timestamp'] = transaction.timestamp.isoformat()
            send_transaction_event(kafka_data)
            logger.info(f"Txn {transaction.id} queued for fraud check")
        except Exception as e:
            logger.error(f"Kafka send failed for txn {transaction.id}: {e}")

        # Merge serializer.data + UI fields
        response_data = serializer.data
        response_data.update({
            "status": "processing",
            "message": "Transaction queued for fraud analysis. Refresh in 2 seconds.",
            "check_url": f"/api/fraud/transactions/{transaction.id}/"
        })

        headers = self.get_success_headers(serializer.data)
        return Response(response_data, status=status.HTTP_202_ACCEPTED, headers=headers)