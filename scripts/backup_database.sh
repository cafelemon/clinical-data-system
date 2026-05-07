#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-${ROOT_DIR}/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="${BACKUP_ROOT}/db"
OUTPUT_FILE="${OUTPUT_DIR}/clinical_data_${TIMESTAMP}.sql"

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGDATABASE="${PGDATABASE:-clinical_data}"
PGUSER="${PGUSER:-clinical_user}"
PGPASSWORD="${PGPASSWORD:-clinical_pass}"

mkdir -p "${OUTPUT_DIR}"

export PGPASSWORD
pg_dump \
  --host "${PGHOST}" \
  --port "${PGPORT}" \
  --username "${PGUSER}" \
  --format plain \
  --file "${OUTPUT_FILE}" \
  "${PGDATABASE}"

echo "Database backup written to ${OUTPUT_FILE}"
