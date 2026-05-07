#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-${ROOT_DIR}/backups}"
FILE_STORAGE_ROOT="${FILE_STORAGE_ROOT:-${ROOT_DIR}/data-dev/file-storage}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="${BACKUP_ROOT}/file-storage/${TIMESTAMP}"

if [[ ! -d "${FILE_STORAGE_ROOT}" ]]; then
  echo "File storage directory does not exist: ${FILE_STORAGE_ROOT}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"
rsync -a --delete "${FILE_STORAGE_ROOT}/" "${OUTPUT_DIR}/"

echo "File storage backup written to ${OUTPUT_DIR}"
