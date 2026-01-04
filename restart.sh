#!/bin/bash

echo "=== Stopping containers ==="
docker-compose down

echo "=== Building images ==="
docker-compose build --no-cache

echo "=== Starting containers ==="
docker-compose up -d

echo "=== Done! Checking status ==="
docker-compose ps
