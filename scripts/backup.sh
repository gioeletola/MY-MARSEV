#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR="${REPO_ROOT}/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.tar.gz"
KEEP_LAST=7

mkdir -p "${BACKUP_DIR}"

echo "Creating backup: ${BACKUP_FILE}"
tar -czf "${BACKUP_FILE}" \
    -C "${REPO_ROOT}" \
    data/ \
    config/

echo "Backup created successfully: ${BACKUP_FILE}"

# Remove old backups, keeping the last KEEP_LAST
BACKUP_COUNT=$(ls -1 "${BACKUP_DIR}"/backup_*.tar.gz 2>/dev/null | wc -l)
if [ "${BACKUP_COUNT}" -gt "${KEEP_LAST}" ]; then
    DELETE_COUNT=$(( BACKUP_COUNT - KEEP_LAST ))
    echo "Removing ${DELETE_COUNT} old backup(s)..."
    ls -1t "${BACKUP_DIR}"/backup_*.tar.gz | tail -n "${DELETE_COUNT}" | xargs rm -f
    echo "Old backups removed."
fi

echo "Done. Backup count: $(ls -1 "${BACKUP_DIR}"/backup_*.tar.gz 2>/dev/null | wc -l)/${KEEP_LAST}"
