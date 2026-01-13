#!/bin/bash

echo "=== Stopping containers ==="
docker-compose down

echo "=== Building images ==="
docker-compose build --no-cache

echo "=== Starting containers ==="
docker-compose up -d

echo "=== Waiting for PostgreSQL to be ready ==="
sleep 3

echo "=== Clearing idempotency keys ==="
docker exec trading_bot_postgres psql -U postgres -d trading_bot -c "DELETE FROM idempotency_keys;" 2>/dev/null || echo "Note: Could not clear idempotency keys (DB might not be ready yet)"

echo "=== Done! Checking status ==="
docker-compose ps
