from pathlib import Path

import httpx


class OcrClientError(RuntimeError):
    pass


class PaddleOcrClient:
    def __init__(self, base_url: str, timeout_seconds: int = 600) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def ocr_pdf_payload(
        self,
        path: Path,
        page_count: int,
        dpi: int,
        include_blocks: bool = False,
    ) -> dict:
        try:
            with path.open("rb") as input_file:
                with httpx.Client(timeout=self.timeout_seconds, trust_env=False) as client:
                    response = client.post(
                        f"{self.base_url}/ocr/pdf",
                        params={
                            "max_pages": page_count,
                            "dpi": dpi,
                            "include_blocks": "true" if include_blocks else "false",
                        },
                        files={"file": (path.name, input_file, "application/pdf")},
                    )
            response.raise_for_status()
        except (OSError, httpx.HTTPError) as exc:
            raise OcrClientError(str(exc)) from exc

        payload = response.json()
        if not isinstance(payload, dict):
            raise OcrClientError("OCR response must be an object")
        return payload

    def ocr_pdf(self, path: Path, page_count: int, dpi: int) -> list[str]:
        payload = self.ocr_pdf_payload(path, page_count=page_count, dpi=dpi)
        pages = payload.get("pages")
        if not isinstance(pages, list):
            raise OcrClientError("OCR response missing pages")
        page_texts = ["" for _ in range(page_count)]
        for page in pages:
            if not isinstance(page, dict):
                continue
            page_no = page.get("page_no")
            text = page.get("text")
            if isinstance(page_no, int) and 1 <= page_no <= page_count and isinstance(text, str):
                page_texts[page_no - 1] = text
        return page_texts
