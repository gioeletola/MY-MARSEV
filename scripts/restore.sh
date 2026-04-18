#!/usr/bin/env bash
set -euo pipefail

BACKUP_FILE="${1:-}"

if [ -z "${BACKUP_FILE}" ]; then
    echo "Usage: $0 <backup-file.tar.gz>" >&2
    exit 1
fi

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Error: Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

# Determine restore target: prefer /app if it exists and is writable, else current dir
if [ -d "/app" ] && [ -w "/app" ]; then
    RESTORE_DIR="/app"
else
    RESTORE_DIR="$(pwd)"
fi

echo "Restoring backup: ${BACKUP_FILE}"
echo "Restore target : ${RESTORE_DIR}"

tar -xzf "${BACKUP_FILE}" -C "${RESTORE_DIR}"

echo "Restore completed successfully."
