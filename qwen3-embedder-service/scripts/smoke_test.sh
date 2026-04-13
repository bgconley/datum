#!/bin/bash
# Smoke test for qwen3-embedder service

set -euo pipefail

BASE_URL="${QWEN_EMBED_URL:-http://localhost:8010}"

echo "=== Qwen3-Embedder Smoke Test ==="
echo "URL: $BASE_URL"
echo ""

# Health check
echo "1. Health check..."
curl -s "$BASE_URL/health" | jq .
echo ""

# Ready check
echo "2. Readiness check..."
READY=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/ready")
if [ "$READY" = "200" ]; then
    echo "   Service is ready"
    curl -s "$BASE_URL/ready" | jq .
else
    echo "   Service not ready (status: $READY)"
    exit 1
fi
echo ""

# Models endpoint
echo "3. List models..."
curl -s "$BASE_URL/v1/models" | jq .
echo ""

# Config endpoint
echo "4. Get config..."
curl -s "$BASE_URL/v1/config" | jq .
echo ""

# Single text embedding
echo "5. Single text embedding..."
RESPONSE=$(curl -s -X POST "$BASE_URL/v1/embeddings" \
    -H "Content-Type: application/json" \
    -d '{"input": "Hello, world!"}')
echo "$RESPONSE" | jq '{object, model, usage, embedding_dim: .data[0].embedding | length}'
echo ""

# Multiple texts embedding
echo "6. Multiple texts embedding..."
RESPONSE=$(curl -s -X POST "$BASE_URL/v1/embeddings" \
    -H "Content-Type: application/json" \
    -d '{
        "input": [
            "What is machine learning?",
            "Machine learning is a subset of artificial intelligence.",
            "The weather is nice today."
        ],
        "instruction": "Given a query, retrieve relevant passages"
    }')
echo "$RESPONSE" | jq '{object, model, usage, num_embeddings: .data | length}'
echo ""

# MRL truncation
echo "7. MRL dimension truncation (512 dims)..."
RESPONSE=$(curl -s -X POST "$BASE_URL/v1/embeddings" \
    -H "Content-Type: application/json" \
    -d '{
        "input": "Test MRL truncation",
        "dimensions": 512
    }')
echo "$RESPONSE" | jq '{model, embedding_dim: .data[0].embedding | length}'
echo ""

echo "=== Smoke Test Complete ==="
