# LEDGERX - Real-Time Fraud Detection API

Enterprise-grade fraud detection backend using Django REST Framework, Apache Kafka, PostgreSQL, and Redis.

## Tech Stack
- **Framework**: Django 4.2 + Django REST Framework
- **Streaming**: Apache Kafka 3.7 with async producers/consumers
- **Database**: PostgreSQL 16
- **Cache/Queue**: Redis 7 for real-time fraud scoring
- **API**: RESTful endpoints via DRF

## Architecture
1. Transaction POST to `/api/transactions/`
2. Kafka producer streams to `transactions` topic
3. Redis caches user transaction history for velocity checks
4. Async consumer applies fraud rules: geo-velocity, amount anomaly, device fingerprint
5. Flagged transactions stored in PostgreSQL
6. Query flagged data via `/api/fraud-alerts/`

## Demo

### 1. Multi-Rule Fraud Detection
(screenshots/DRF API Response.png)
API flags `darkweb` merchant. Rules: `velocity_rule+time_anomaly+ml_model+blacklist_merchant`

### 2. Fraud Monitoring Dashboard
(screenshots/Django Admin.png)
Django admin tracks 24 transactions. Rule engine detects velocity + blacklist patterns. 

### 3. Real-Time Streaming Pipeline
(screenshots/Kafka + Redis Consumer.png)
Async Kafka consumer connected to Kafka + Redis. ML scoring active.

### 4. Automated Tests Passing
(screenshots/Test Passing.png)
Unit tests validate core fraud logic. 4/4 tests passed. 

## Quick Start
```bash
# Setup PostgreSQL
createdb ledgerx_db

# Start Redis
redis-server

# Backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Terminal 2 - Start Kafka
bin/kafka-server-start.sh config/server.properties

# Terminal 3 - Start consumer
python manage.py run_consumer
