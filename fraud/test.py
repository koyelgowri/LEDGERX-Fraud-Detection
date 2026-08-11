from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch
from decimal import Decimal
from.models import Transaction

class TransactionAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/fraud/transactions/'

    @patch('fraud.views.send_transaction_event')
    def test_create_transaction_returns_202(self, mock_kafka):
        data = {
            "amount": 100.00,
            "merchant": "amazon",
            "user_id": 1,
            "idempotency_key": "TEST_001"
        }
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertFalse(response.data['is_fraud'])
        self.assertIsNone(response.data['fraud_score'])
        self.assertEqual(response.data['rule_triggered'], 'pending')
        self.assertEqual(response.data['idempotency_key'], 'TEST_001')
        mock_kafka.assert_called_once()

    def test_negative_amount_rejected(self):
        data = {"amount": -50, "merchant": "test", "user_id": 1, "idempotency_key": "TEST_002"}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('fraud.views.send_transaction_event')
    def test_duplicate_idempotency_key_rejected(self, mock_kafka):
        data = {"amount": 100, "merchant": "test", "user_id": 1, "idempotency_key": "DUPLICATE"}
        self.client.post(self.url, data, format='json')
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('fraud.views.send_transaction_event')
    def test_latest_filter_returns_one(self, mock_kafka):
        Transaction.objects.create(
            amount=Decimal('100.00'), merchant="old", user_id=1,
            idempotency_key="OLD", is_fraud=False, rule_triggered='none'
        )
        Transaction.objects.create(
            amount=Decimal('200.00'), merchant="new", user_id=1,
            idempotency_key="NEW", is_fraud=True, rule_triggered='blacklist_merchant'
        )
        response = self.client.get(f"{self.url}?latest=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['merchant'], "new")