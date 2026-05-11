#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PADDLE_OCR_DIR="${PADDLE_OCR_DIR:-/Users/jiafei/workspace/paddle-ocr-api}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT_DIR/backups/migration/offline-gpu}"
VERSION="${VERSION:-$(date +%Y%m%d)-paddle331-cu129}"
SAMPLE_PDF="${SAMPLE_PDF:-$ROOT_DIR/010001.pdf}"
CPU_OCR_IMAGE="${CPU_OCR_IMAGE:-paddle-ocr-api-paddle-ocr-api:latest}"
PADDLE_VERSION="${PADDLE_VERSION:-3.3.1}"
PADDLE_GPU_INDEX_URL="${PADDLE_GPU_INDEX_URL:-https://www.paddlepaddle.org.cn/packages/stable/cu129/}"

IMAGE_TAR="$OUTPUT_ROOT/clinical-data-gpu-images-${VERSION}.tar"
IMAGE_ARCHIVE="${IMAGE_TAR}.gz"
CACHE_ROOT="$OUTPUT_ROOT/paddle-ocr-cache-${VERSION}"
CACHE_ARCHIVE="$OUTPUT_ROOT/paddle-ocr-model-cache-${VERSION}.tar.gz"
CHECKSUM_FILE="$OUTPUT_ROOT/SHA256SUMS-${VERSION}.txt"

BACKEND_IMAGE="clinical-backend:${VERSION}"
FRONTEND_IMAGE="clinical-frontend:${VERSION}"
OCR_GPU_IMAGE="paddle-ocr-api-gpu:${VERSION}"
OCR_GPU_IMAGE_STABLE="${OCR_GPU_IMAGE_STABLE:-paddle-ocr-api-gpu:latest}"
POSTGRES_IMAGE="postgres:16"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

cleanup_old_outputs() {
  mkdir -p "$OUTPUT_ROOT"

  echo "Remove stale offline GPU bundles under: $OUTPUT_ROOT"
  rm -rf \
    "$OUTPUT_ROOT"/clinical-data-gpu-images-* \
    "$OUTPUT_ROOT"/paddle-ocr-cache-* \
    "$OUTPUT_ROOT"/paddle-ocr-model-cache-* \
    "$OUTPUT_ROOT"/SHA256SUMS*
}

main() {
  require_command docker
  require_command gzip
  require_command tar
  require_command shasum

  if [[ ! -d "$PADDLE_OCR_DIR" ]]; then
    echo "Paddle OCR directory not found: $PADDLE_OCR_DIR" >&2
    exit 1
  fi
  if [[ ! -f "$SAMPLE_PDF" ]]; then
    echo "Sample PDF not found: $SAMPLE_PDF" >&2
    exit 1
  fi

  cleanup_old_outputs
  mkdir -p "$OUTPUT_ROOT" "$CACHE_ROOT/model_cache/paddlex" "$CACHE_ROOT/model_cache/paddle"

  echo "Build linux/amd64 backend image: $BACKEND_IMAGE"
  docker buildx build --platform linux/amd64 --provenance=false --load -t "$BACKEND_IMAGE" "$ROOT_DIR/backend"

  echo "Build linux/amd64 frontend image: $FRONTEND_IMAGE"
  docker buildx build --platform linux/amd64 --provenance=false --load -t "$FRONTEND_IMAGE" "$ROOT_DIR/frontend"

  echo "Build linux/amd64 GPU OCR image: $OCR_GPU_IMAGE"
  docker buildx build \
    --platform linux/amd64 \
    --provenance=false \
    --load \
    --build-arg "PADDLE_VERSION=$PADDLE_VERSION" \
    --build-arg "PADDLE_GPU_INDEX_URL=$PADDLE_GPU_INDEX_URL" \
    -f "$ROOT_DIR/deploy/offline/paddle-ocr-api-gpu.Dockerfile" \
    -t "$OCR_GPU_IMAGE" \
    "$PADDLE_OCR_DIR"

  echo "Tag GPU OCR image with stable alias: $OCR_GPU_IMAGE_STABLE"
  docker tag "$OCR_GPU_IMAGE" "$OCR_GPU_IMAGE_STABLE"

  echo "Build linux/amd64 postgres image: $POSTGRES_IMAGE"
  docker buildx build \
    --platform linux/amd64 \
    --provenance=false \
    --load \
    -f "$ROOT_DIR/deploy/offline/postgres-offline.Dockerfile" \
    -t "$POSTGRES_IMAGE" \
    "$ROOT_DIR/deploy/offline"

  echo "Pre-download PaddleOCR model cache with CPU image: $CPU_OCR_IMAGE"
  docker run --rm -i \
    -e PADDLE_PDX_MODEL_SOURCE=bos \
    -e PADDLEX_MODEL_HEALTHCHECK_TIMEOUT=10 \
    -v "$CACHE_ROOT/model_cache/paddlex:/root/.paddlex" \
    -v "$CACHE_ROOT/model_cache/paddle:/root/.cache/paddle" \
    -v "$SAMPLE_PDF:/tmp/sample.pdf:ro" \
    "$CPU_OCR_IMAGE" \
    python - <<'PY'
from pathlib import Path

from app.main import _ocr_pdf_bytes

pdf_path = Path("/tmp/sample.pdf")
result = _ocr_pdf_bytes(
    pdf_bytes=pdf_path.read_bytes(),
    filename=pdf_path.name,
    content_type="application/pdf",
    max_pages=1,
    dpi=120,
    include_blocks=False,
)
print({"processed_pages": result.get("processed_pages"), "text_len": len(result["pages"][0].get("text", ""))})
PY

  echo "Archive PaddleOCR model cache"
  tar -czf "$CACHE_ARCHIVE" -C "$CACHE_ROOT" model_cache

  echo "Save Docker images"
  rm -f "$IMAGE_TAR" "$IMAGE_ARCHIVE"
  docker save "$POSTGRES_IMAGE" "$BACKEND_IMAGE" "$FRONTEND_IMAGE" "$OCR_GPU_IMAGE" "$OCR_GPU_IMAGE_STABLE" -o "$IMAGE_TAR"
  gzip -9 "$IMAGE_TAR"

  echo "Write checksums"
  (
    cd "$OUTPUT_ROOT"
    shasum -a 256 \
      "$(basename "$IMAGE_ARCHIVE")" \
      "$(basename "$CACHE_ARCHIVE")" \
      > "$(basename "$CHECKSUM_FILE")"
  )

  echo "Done:"
  echo "  $IMAGE_ARCHIVE"
  echo "  $CACHE_ARCHIVE"
  echo "  $CHECKSUM_FILE"
  echo
  echo "Images:"
  echo "  $POSTGRES_IMAGE"
  echo "  $BACKEND_IMAGE"
  echo "  $FRONTEND_IMAGE"
  echo "  $OCR_GPU_IMAGE"
  echo "  $OCR_GPU_IMAGE_STABLE"
  echo
  echo "Paddle GPU build args:"
  echo "  PADDLE_VERSION=$PADDLE_VERSION"
  echo "  PADDLE_GPU_INDEX_URL=$PADDLE_GPU_INDEX_URL"
}

main "$@"
