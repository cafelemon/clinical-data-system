#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PADDLE_OCR_DIR="${PADDLE_OCR_DIR:-/Users/jiafei/workspace/paddle-ocr-api}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT_DIR/backups/migration}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
PACKAGE_NAME="clinical-data-linux-migration-${TIMESTAMP}"
WORK_DIR="$OUTPUT_ROOT/$PACKAGE_NAME"
ARCHIVE_PATH="$OUTPUT_ROOT/${PACKAGE_NAME}.tar.gz"

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-clinical-postgres-dev}"
POSTGRES_USER="${POSTGRES_USER:-clinical_user}"
POSTGRES_DB="${POSTGRES_DB:-clinical_data}"
FILE_STORAGE_DIR="${FILE_STORAGE_DIR:-$ROOT_DIR/data-dev/file-storage}"
PADDLE_OCR_RUNTIME_DIR="${PADDLE_OCR_RUNTIME_DIR:-$ROOT_DIR/runtime/paddle-ocr}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

copy_tree() {
  local source_dir="$1"
  local target_dir="$2"

  mkdir -p "$target_dir"
  rsync -a \
    --exclude '.git/' \
    --exclude '.DS_Store' \
    --include '**/.env.example' \
    --exclude '**/.env' \
    --exclude '**/.env.*' \
    --exclude '.venv/' \
    --exclude 'env/' \
    --exclude 'node_modules/' \
    --exclude 'dist/' \
    --exclude 'build/' \
    --exclude '.pytest_cache/' \
    --exclude '.ruff_cache/' \
    --exclude '__pycache__/' \
    --exclude 'data-dev/' \
    --exclude 'backups/' \
    --exclude 'postgres-data/' \
    --exclude 'file-storage/' \
    --exclude 'logs/' \
    --exclude 'ocr_outputs/' \
    --exclude 'model_cache/' \
    --exclude '010001.pdf' \
    "$source_dir"/ "$target_dir"/
}

write_bundle_readme() {
  cat > "$WORK_DIR/README_MIGRATION_BUNDLE.txt" <<EOF
临床数据系统 Linux 迁移包

生成时间: $TIMESTAMP

目录说明:
- clinical-data-system/: 临床数据系统源码和部署文件
- paddle-ocr-api/: PaddleOCR 本地 API 服务源码
- database/clinical_data.sql: 当前 PostgreSQL 逻辑备份
- runtime/file-storage/: 当前文件存储目录备份
- runtime/paddle-ocr/: OCR 运行目录占位，含模型缓存与输出目录
- SHA256SUMS: 包内文件校验值

服务器部署步骤请阅读:
clinical-data-system/docs/linux_migration_paddle_ocr_and_clinical_system.md
EOF
}

main() {
  require_command rsync
  require_command tar
  require_command docker
  require_command shasum

  if [[ ! -d "$PADDLE_OCR_DIR" ]]; then
    echo "Paddle OCR directory not found: $PADDLE_OCR_DIR" >&2
    echo "Set PADDLE_OCR_DIR=/path/to/paddle-ocr-api and rerun." >&2
    exit 1
  fi

  rm -rf "$WORK_DIR"
  mkdir -p "$WORK_DIR/database" "$WORK_DIR/runtime" "$OUTPUT_ROOT"

  echo "Copy clinical-data-system source..."
  copy_tree "$ROOT_DIR" "$WORK_DIR/clinical-data-system"

  echo "Copy paddle-ocr-api source..."
  copy_tree "$PADDLE_OCR_DIR" "$WORK_DIR/paddle-ocr-api"

  echo "Dump PostgreSQL database from container: $POSTGRES_CONTAINER..."
  docker exec "$POSTGRES_CONTAINER" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
    > "$WORK_DIR/database/clinical_data.sql"

  echo "Copy file storage..."
  mkdir -p "$WORK_DIR/runtime/file-storage"
  if [[ -d "$FILE_STORAGE_DIR" ]]; then
    rsync -a "$FILE_STORAGE_DIR"/ "$WORK_DIR/runtime/file-storage"/
  else
    echo "File storage directory not found, created empty directory: $FILE_STORAGE_DIR" >&2
  fi

  mkdir -p \
    "$WORK_DIR/runtime/postgres-data" \
    "$WORK_DIR/runtime/paddle-ocr/test_data" \
    "$WORK_DIR/runtime/paddle-ocr/ocr_outputs" \
    "$WORK_DIR/runtime/paddle-ocr/model_cache/paddlex" \
    "$WORK_DIR/runtime/paddle-ocr/model_cache/paddle"

  echo "Copy PaddleOCR runtime cache..."
  if [[ -d "$PADDLE_OCR_RUNTIME_DIR" ]]; then
    rsync -a \
      "$PADDLE_OCR_RUNTIME_DIR"/ \
      "$WORK_DIR/runtime/paddle-ocr"/
  else
    echo "Paddle OCR runtime directory not found, kept empty runtime skeleton: $PADDLE_OCR_RUNTIME_DIR" >&2
  fi

  write_bundle_readme

  echo "Write checksums..."
  (
    cd "$WORK_DIR"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 shasum -a 256 > SHA256SUMS
  )

  echo "Create archive..."
  (
    cd "$OUTPUT_ROOT"
    tar -czf "$ARCHIVE_PATH" "$PACKAGE_NAME"
  )

  echo "Done:"
  echo "$ARCHIVE_PATH"
}

main "$@"
