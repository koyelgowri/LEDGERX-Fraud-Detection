import json
import os
import sys
import django
import logging
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from datetime import datetime
import redis
from django.db import transaction

# Django setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LEDGERX.settings')
django.setup()

from fraud.models import Transaction
from fraud.ml_model import predict_fraud
from fraud.rules import check_velocity, check_amount_threshold, check_time_anomaly

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s  %(message)s'
)
logger = logging.getLogger(__name__)

# Kafka Consumer
try:
    consumer = KafkaConsumer(
        'transactions',
        bootstrap_servers='localhost:9092',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='latest',  # Only process new messages
        enable_auto_commit=True,
        group_id='ledgerx-consumer-v3',  # Fresh consumer group
        session_timeout_ms=45000,
        heartbeat_interval_ms=15000,
        request_timeout_ms=50000,
        api_version=(3, 6)  # Match your KRaft 4.3.1
    )
    logger.info("Connected to Kafka successfully")
except KafkaError as e:
    logger.error(f"Failed to connect to Kafka: {e}")
    sys.exit(1)

# Redis for velocity checks
try:
    from fraud.redis_client import redis_client as r
    r.ping()  # Test connection
    logger.info("Connected to Redis successfully")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    sys.exit(1)

logger.info("🚀 LedgerX ML Fraud Consumer started...")

for message in consumer:
    try:
        data = message.value
        logger.info(f"📥 Transaction received: {data}")

        # 1. VALIDATE REQUIRED FIELDS
        idempotency_key = data.get('idempotency_key')
        amount = float(data.get('amount', 0))
        user_id = data.get('user_id')
        merchant = data.get('merchant', 'unknown')
        
        if not all([idempotency_key, amount, user_id]):
            logger.error(f"Missing required fields: {data}")
            continue

        # Parse timestamp from producer, fallback to now
        try:
            txn_timestamp = datetime.fromisoformat(data.get('timestamp'))
            hour = txn_timestamp.hour
        except (TypeError, ValueError):
            txn_timestamp = datetime.now()
            hour = txn_timestamp.hour

        # 2. VELOCITY CHECK - Redis
        is_velocity_fraud, velocity_count = check_velocity(user_id)
        
        # 3. ML PREDICTION - with fail-safe
        try:
            ml_is_fraud, fraud_score, ml_details = predict_fraud(
                amount=amount,
                hour=hour,
                velocity_count=velocity_count,
                merchant=merchant
            )
        except Exception as ml_error:
            logger.warning(f"ML model failed: {ml_error}. Using rules only.")
            ml_is_fraud, fraud_score, ml_details = False, 0.0, {
                "status": "ml_error", 
                "error": str(ml_error),
                "model": "IsolationForest_v1"
            }

        # 4. RULE ENGINE - Clean, no duplicate logic
        rule_list = []
        final_is_fraud = False

        # Rule 1: Amount threshold
        if check_amount_threshold(amount):
            rule_list.append("amount_threshold")
            final_is_fraud = True

        # Rule 2: Velocity threshold  
        if is_velocity_fraud:
            rule_list.append("velocity_rule")
            final_is_fraud = True

        # Rule 3: Time anomaly
        if check_time_anomaly(hour):
            rule_list.append("time_anomaly")
            final_is_fraud = True

        # Rule 4: ML Model
        if ml_is_fraud:
            rule_list.append("ml_model")
            final_is_fraud = True

        # Rule 5: Blacklist merchant - bonus rule
        if merchant.lower() in ['darkweb', 'casino', 'unknown']:
            rule_list.append("blacklist_merchant")
            final_is_fraud = True

        rule = "+".join(rule_list) if rule_list else "passed"

        # 5. DB UPDATE - Atomic, safe, using idempotency_key
        with transaction.atomic():
            updated = Transaction.objects.filter(
                idempotency_key=idempotency_key
            ).update(
                is_fraud=final_is_fraud,
                fraud_score=round(fraud_score, 4),
                rule_triggered=rule,
                merchant=merchant,
                ml_prediction=ml_details,
                timestamp=txn_timestamp,
                amount=amount,
                user_id=user_id
            )
            
            if updated == 0:
                logger.warning(f"Transaction {idempotency_key} not found. Creating new record.")
                obj, created = Transaction.objects.get_or_create(
                    idempotency_key=idempotency_key,
                    defaults={
                        'user_id': user_id,
                        'amount': amount,
                        'merchant': merchant,
                        'timestamp': txn_timestamp,
                        'is_fraud': final_is_fraud,
                        'fraud_score': round(fraud_score, 4),
                        'rule_triggered': rule,
                        'ml_prediction': ml_details
                    }
                )
                if not created:
                    logger.info(f"Race condition: {idempotency_key} already created. Updating.")
                    Transaction.objects.filter(idempotency_key=idempotency_key).update(
                        is_fraud=final_is_fraud,
                        fraud_score=round(fraud_score, 4),
                        rule_triggered=rule,
                        ml_prediction=ml_details
                    )

        logger.info(f"🤖 Result: key={idempotency_key} fraud={final_is_fraud}, score={fraud_score:.4f}, rule={rule}")
        logger.info(f" Amount: ₹{amount:,.2f}, Velocity: {velocity_count}, ML_Flag: {ml_is_fraud}")

    except Exception as e:
        logger.error(f"Error processing message {data}: {e}", exc_info=True)
        continue