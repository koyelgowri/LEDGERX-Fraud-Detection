import psycopg2, redis, json
from kafka import KafkaProducer

print("Checking LEDGERX stack...")

# Postgres - update user/pass to match your install
try:
    conn = psycopg2.connect(
        dbname="ledgerx", 
        user="postgres", 
        password="postgres",  # <- Change this to your Postgres password
        host="localhost", 
        port=5432
    )
    print("Postgres :5432 ✅")
    conn.close()
except Exception as e: 
    print(f"Postgres :5432 ❌ {e}")

# Redis   
try:
    r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=1, protocol=2)
    r.ping()
    print("Redis :6379 ✅")
except Exception as e: 
    print(f"Redis :6379 ❌ {e}")

# Kafka
try:
    p = KafkaProducer(bootstrap_servers='localhost:9092', request_timeout_ms=1000)
    p.close()
    print("Kafka :9092 ✅")
except Exception as e: 
    print(f"Kafka :9092 ❌ {e}")

print("Stack check complete")