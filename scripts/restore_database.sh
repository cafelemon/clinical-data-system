#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/clinical_data_YYYYmmdd_HHMMSS.sql" >&2
  exit 1
fi

DUMP_FILE="$1"
if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "Dump file does not exist: ${DUMP_FILE}" >&2
  exit 1
fi

if [[ "${CONFIRM_RESTORE:-}" != "yes" ]]; then
  echo "Set CONFIRM_RESTORE=yes to restore into the target database." >&2
  exit 1
fi

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGDATABASE="${PGDATABASE:-clinical_data}"
PGUSER="${PGUSER:-clinical_user}"
PGPASSWORD="${PGPASSWORD:-clinical_pass}"

export PGPASSWORD
psql \
  --host "${PGHOST}" \
  --port "${PGPORT}" \
  --username "${PGUSER}" \
  --dbname "${PGDATABASE}" \
  --file "${DUMP_FILE}"

echo "Database restored from ${DUMP_FILE}"
