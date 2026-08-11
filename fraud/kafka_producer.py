import json
import os
import logging
from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)
_producer = None

def get_producer():
    global _producer
    if _producer is None:
        try:
            _producer = KafkaProducer(
                bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                # Prod settings
                acks='all',  # Wait for all replicas = no data loss
                retries=3,   # Retry on transient errors
                linger_ms=10, # Batch messages for 10ms = better throughput
                request_timeout_ms=30000,
                max_block_ms=5000,  # Don't block API >5s if Kafka down
                compression_type='gzip'
            )
            logger.info("Kafka producer connected")
        except KafkaError as e:
            logger.error(f"Failed to init Kafka producer: {e}")
            _producer = None
    return _producer

def send_transaction_event(data):
    """
    Send txn to Kafka. Non-blocking. Returns True/False for success.
    Call this from your API view after Transaction.objects.create()
    """
    producer = get_producer()
    if producer is None:
        logger.error("Kafka producer not available. Skipping event.")
        return False
    
    try:
        # Add event metadata
        event = {
            **data,
            "event_type": "transaction.created",
            "version": "v1"
        }
        
        # Send async - don't block API
        future = producer.send('transactions', value=event, key=str(data.get('id')).encode())
        
        # Optional: add callback for delivery confirmation
        future.add_callback(on_send_success)
        future.add_errback(on_send_error)
        
        return True
    except Exception as e:
        logger.error(f"Failed to send Kafka event: {e}", exc_info=True)
        return False

def on_send_success(record_metadata):
    logger.debug(f"Event sent to {record_metadata.topic} partition {record_metadata.partition} offset {record_metadata.offset}")

def on_send_error(excp):
    logger.error(f"Failed to deliver Kafka event: {excp}")

def close_producer():
    """Call on Django shutdown"""
    global _producer
    if _producer:
        _producer.flush(timeout=10)
        _producer.close(timeout=10)
        _producer = None