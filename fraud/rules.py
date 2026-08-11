from.redis_client import redis_client
import logging

logger = logging.getLogger(__name__)

MAX_TRANSACTIONS = 5 # Changed from 2 - 2 is too strict for testing
WINDOW_SECONDS = 3600 # 1 hour window like your consumer uses

def check_velocity(user_id):
    """
    Returns True if user exceeded velocity limit = should flag as fraud
    Uses pipeline to avoid race conditions
    """
    key = f"fraud:user:{user_id}:velocity"
    
    try:
        # Pipeline = all commands run as 1 atomic operation
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, WINDOW_SECONDS) # Always refresh expiry
        results = pipe.execute()
        
        count = results[0] # Result of incr
        
        logger.debug(f"Redis key: {key}, Count: {count}")
        
        is_exceeded = count > MAX_TRANSACTIONS
        
        if is_exceeded:
            logger.warning(f"Velocity limit exceeded for user {user_id}: {count}/{MAX_TRANSACTIONS}")
        
        return is_exceeded, count # Return count too for ML features
        
    except Exception as e:
        logger.error(f"Redis velocity check failed for user {user_id}: {e}")
        # Fail open: if Redis is down, don't block legit transactions
        return False, 0

def check_amount_threshold(amount, threshold=50000):
    """Rule 1: Flag high value transactions"""
    return float(amount) > threshold

def check_time_anomaly(hour):
    """Rule 3: Flag weird hours 1am-5am"""
    return hour >= 1 and hour <= 5