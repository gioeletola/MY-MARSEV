#!/usr/bin/env bash
set -euo pipefail

HEALTH_URL="http://localhost:8080/health"
TIMEOUT=5

RESPONSE=$(curl -sf --max-time "${TIMEOUT}" "${HEALTH_URL}" 2>/dev/null || true)

if echo "${RESPONSE}" | grep -qi "ok"; then
    echo "Health check passed: ${RESPONSE}"
    exit 0
else
    echo "Health check failed. Response: ${RESPONSE:-<no response>}" >&2
    exit 1
fi
