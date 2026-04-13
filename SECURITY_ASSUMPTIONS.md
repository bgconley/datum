# Security Assumptions and Accepted Risks

This repository intentionally runs the Datum inference services (`qwen3-embedder-service`, `qwen3-reranker-service`) without request authentication.

## Accepted by design

- `qwen3-embedder-service` and `qwen3-reranker-service` do **not** enforce API keys, session auth, or mTLS.
- This is an explicit product decision for low-latency private-network inference paths.

## Required deployment assumptions

- Services run only on trusted private infrastructure.
- Network exposure is controlled by host/network policy (private subnet, firewall, or equivalent controls).
- Reverse-proxy and port-publish choices are constrained to intended consumers.

## Operational implications

- Any network principal that can reach the inference ports can consume GPU inference resources.
- Capacity abuse prevention is currently handled operationally (network policy and service sizing), not via application-layer auth.

## Phase impact

- This document records a conscious risk acceptance for Phase 4 planning.
- If deployment scope changes beyond private/trusted networks, this decision must be revisited and tracked as a new hardening task.
