import redis
import os
import logging

logger = logging.getLogger(__name__)

# Connection pool = reuses connections instead of making new one per request
redis_pool = redis.ConnectionPool(
    host=os.environ.get("REDIS_HOST", "localhost"),  # "redis" in Docker, "localhost" locally
    port=int(os.environ.get("REDIS_PORT", 6379)),
    db=int(os.environ.get("REDIS_DB", 0)),
    decode_responses=True,
    max_connections=20,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True
)

redis_client = redis.Redis(connection_pool=redis_pool)

def check_redis_connection():
    """Call this on startup to fail fast if Redis is down"""
    try:
        redis_client.ping()
        logger.info("✅ Redis connected")
        return True
    except redis.ConnectionError as e:
        logger.error(f"❌ Redis connection failed: {e}")
        return False

# Test connection on import
check_redis_connection()