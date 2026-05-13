#!/usr/bin/env python3
"""macOS Vision OCR API for local Apple Silicon sample development.

This service intentionally mirrors the small subset of the Paddle OCR API used
by the clinical backend: /health and /ocr/pdf.
"""

from __future__ import annotations

import os
import platform
import tempfile
import time
from typing import Any

import fitz
import Vision
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from Foundation import NSData


DEFAULT_LANGUAGES = ("zh-Hans", "en-US")

app = FastAPI(
    title="macOS Vision OCR Local API",
    description="Local OCR API backed by Apple Vision for sample development on Mac.",
    version="0.1.0",
)


def recognition_languages() -> list[str]:
    raw = os.getenv("MAC_VISION_OCR_LANGUAGES", ",".join(DEFAULT_LANGUAGES))
    return [item.strip() for item in raw.split(",") if item.strip()]


def recognition_level() -> int:
    raw = os.getenv("MAC_VISION_OCR_LEVEL", "accurate").strip().lower()
    if raw == "fast":
        return Vision.VNRequestTextRecognitionLevelFast
    return Vision.VNRequestTextRecognitionLevelAccurate


def render_pdf_pages(pdf_bytes: bytes, max_pages: int, dpi: int) -> list[bytes]:
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to open PDF: {exc}") from exc

    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    pages: list[bytes] = []
    try:
        for page_index in range(min(max_pages, document.page_count)):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            pages.append(pixmap.tobytes("png"))
    finally:
        document.close()
    return pages


def candidate_text(candidate: Any) -> str:
    value = candidate.string()
    return str(value) if value is not None else ""


def candidate_confidence(candidate: Any) -> float | None:
    try:
        return float(candidate.confidence())
    except Exception:
        return None


def observation_box(observation: Any) -> dict[str, float] | None:
    try:
        box = observation.boundingBox()
        return {
            "x": float(box.origin.x),
            "y": float(box.origin.y),
            "width": float(box.size.width),
            "height": float(box.size.height),
        }
    except Exception:
        return None


def recognize_png_bytes(png_bytes: bytes, include_blocks: bool) -> dict[str, Any]:
    data = NSData.dataWithBytes_length_(png_bytes, len(png_bytes))
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(recognition_level())
    request.setUsesLanguageCorrection_(True)
    request.setRecognitionLanguages_(recognition_languages())

    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, {})
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise HTTPException(status_code=502, detail=f"Vision OCR failed: {error}")

    texts: list[str] = []
    scores: list[float] = []
    blocks: list[dict[str, Any]] = []
    for observation in request.results() or []:
        candidates = observation.topCandidates_(1)
        if not candidates:
            continue
        candidate = candidates[0]
        text = candidate_text(candidate)
        confidence = candidate_confidence(candidate)
        if text:
            texts.append(text)
        if confidence is not None:
            scores.append(confidence)
        if include_blocks:
            blocks.append(
                {
                    "text": text,
                    "confidence": confidence,
                    "box": observation_box(observation),
                }
            )

    result: dict[str, Any] = {
        "text": "\n".join(texts),
        "avg_confidence": sum(scores) / len(scores) if scores else None,
        "block_count": len(blocks) if include_blocks else len(texts),
    }
    if include_blocks:
        result["blocks"] = blocks
    return result


def validate_pdf_upload(file: UploadFile) -> None:
    if file.content_type in {"application/pdf", "application/x-pdf", "application/octet-stream"}:
        return
    if file.filename and file.filename.lower().endswith(".pdf"):
        return
    raise HTTPException(status_code=400, detail=f"Only PDF files are supported. Got: {file.content_type}")


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "service": "mac-vision-ocr-api",
            "version": "0.1.0",
            "backend": "apple_vision",
            "platform": platform.platform(),
            "machine": platform.machine(),
            "recognition_languages": recognition_languages(),
            "recognition_level": os.getenv("MAC_VISION_OCR_LEVEL", "accurate"),
        }
    )


@app.post("/ocr/pdf")
async def ocr_pdf(
    file: UploadFile = File(...),
    max_pages: int = Query(default=1, ge=1, le=300),
    dpi: int = Query(default=120, ge=80, le=220),
    include_blocks: bool = Query(default=False),
) -> JSONResponse:
    validate_pdf_upload(file)
    pdf_bytes = await file.read()
    start = time.time()
    pages = render_pdf_pages(pdf_bytes, max_pages=max_pages, dpi=dpi)

    page_results: list[dict[str, Any]] = []
    for page_no, png_bytes in enumerate(pages, start=1):
        result = recognize_png_bytes(png_bytes, include_blocks=include_blocks)
        page_item: dict[str, Any] = {
            "page_no": page_no,
            "text": result.get("text", ""),
            "avg_confidence": result.get("avg_confidence"),
            "block_count": result.get("block_count", 0),
        }
        if include_blocks:
            page_item["blocks"] = result.get("blocks", [])
        page_results.append(page_item)

    return JSONResponse(
        {
            "filename": file.filename,
            "content_type": file.content_type,
            "dpi": dpi,
            "requested_max_pages": max_pages,
            "processed_pages": len(page_results),
            "elapsed_seconds": round(time.time() - start, 3),
            "pages": page_results,
        }
    )


@app.post("/ocr/pdf/save")
async def ocr_pdf_save(
    file: UploadFile = File(...),
    max_pages: int = Query(default=1, ge=1, le=300),
    dpi: int = Query(default=120, ge=80, le=220),
    include_blocks: bool = Query(default=False),
) -> JSONResponse:
    response = await ocr_pdf(file=file, max_pages=max_pages, dpi=dpi, include_blocks=include_blocks)
    payload = response.body.decode("utf-8")
    output_dir = os.getenv("MAC_VISION_OCR_OUTPUT_DIR", "/tmp/mac-vision-ocr")
    os.makedirs(output_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename or "unknown.pdf").replace(" ", "_")
    output_path = os.path.join(output_dir, f"{int(time.time())}_{safe_name}.ocr.json")
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(payload)
    return JSONResponse(
        {
            "status": "saved",
            "filename": file.filename,
            "result_path_on_mac": output_path,
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("MAC_VISION_OCR_PORT", "8048")))
