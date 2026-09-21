"""L2 pdf port: PyMuPDF text layer first, MinerU probe-degraded second.

Output contract borrows docling's ExtractedPageData shape (per-page text +
per-page errors) and marker's channel layering: channel/convert/render stay
separate so MinerU can replace the convert step without touching callers.
PyMuPDF is AGPL-3.0: used as a library only, none of its code is copied here;
core stays stdlib-only (fitz is imported lazily, absence is an envelope).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import canon, store


def _fail(error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": error, **extra}


def _import_fitz() -> Any | None:
    """Lazy PyMuPDF seam (tests monkeypatch this; production imports fitz)."""
    try:
        import pymupdf  # type: ignore[import-not-found]

        return pymupdf
    except ImportError:
        try:
            import fitz  # type: ignore[import-not-found]

            return fitz
        except ImportError:
            return None


def _mineru_available() -> bool:
    """Cold-start-scale probe: import only, never blocks the text layer."""
    try:
        import mineru  # type: ignore[import-not-found]  # noqa: F401

        return True
    except ImportError:
        return False


def extract(path_str: str, max_pages: int = 0) -> dict[str, Any]:
    """Extract {text_md, pages[{page_no, raw_text, errors}], fallback}. No raise."""
    if canon.is_forbidden(path_str):
        return _fail(f"pdf inside a forbidden root: {path_str}")
    path = Path(path_str)
    if not path.is_file():
        return _fail(f"pdf not found: {path_str}")
    fitz = _import_fitz()
    fallback = [f"mineru-{'ready' if _mineru_available() else 'unavailable'}"]
    if fitz is None:
        fallback.append("pymupdf-missing")
        return _fail("PyMuPDF not installed (pdf extra); text layer unavailable",
                     fallback_chain=fallback)
    try:
        doc = fitz.open(stream=store.read_bytes(path), filetype="pdf")
    except Exception as exc:
        return _fail(f"pdf open failed: {type(exc).__name__}: {exc}",
                     fallback_chain=fallback)
    pages: list[dict[str, Any]] = []
    try:
        total = doc.page_count
        limit = total if not max_pages or max_pages <= 0 else min(total, max_pages)
        for n in range(limit):
            try:
                page = doc.load_page(n)
                text = page.get_text("text") or ""
            except Exception as exc:
                pages.append({"page_no": n + 1, "raw_text": "",
                              "errors": [f"{type(exc).__name__}: {exc}"], "needs_ocr": False})
                continue
            if text.strip():
                pages.append({"page_no": n + 1, "raw_text": text,
                              "errors": [], "needs_ocr": False})
                continue
            try:
                has_images = bool(page.get_images())
            except Exception:
                has_images = False
            pages.append({"page_no": n + 1, "raw_text": text,
                          "errors": ["empty-text"], "needs_ocr": has_images})
        try:
            info = dict(doc.metadata or {})
        except Exception:
            info = {}
        meta = {k: str(info.get(k) or "") for k in ("title", "author")}
    finally:
        try:
            doc.close()
        except Exception:
            pass
    text_md = "".join(f"\n\n--- p{p['page_no']} ---\n{p['raw_text']}" for p in pages)
    return {"ok": True, "path": str(path), "pages": len(pages),
            "chars": sum(len(p["raw_text"]) for p in pages),
            "needs_ocr_pages": sum(1 for p in pages if p["needs_ocr"]),
            "meta": meta,
            "text_md": text_md, "page_list": pages,
            "fallback_chain": ["pymupdf-text"] + fallback, "errors": []}
