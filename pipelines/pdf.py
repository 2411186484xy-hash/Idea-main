"""L2 pdf port: integrity gate, text layer, page renders, OA waterfall fetch.

Output contract borrows docling's ExtractedPageData shape (per-page text +
per-page errors) and marker's channel layering: channel/convert/render stay
separate. PyMuPDF is AGPL-3.0: used as a library only, none of its code is
copied here; core stays stdlib-only (fitz is imported lazily, absence is an
envelope). M3.2 adds the V1 completeness gate (LST:1770-1818), the extract
cache the claims page-scope lint reads, and the OA fetch waterfall.
"""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from pathlib import Path
from typing import Any

from . import canon, contracts, net, runs, store


def _fail(error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": error, **extra}


def verify_bytes(blob: bytes) -> tuple[bool, str]:
    """V1 LST:1770-1818 completeness gate: %PDF head, %%EOF tail, min size."""
    min_bytes = int(str(canon.value("pdf.min_bytes")))
    if len(blob) < min_bytes:
        return False, f"too small ({len(blob)} < {min_bytes} bytes)"
    if not blob.startswith(b"%PDF"):
        return False, "missing %PDF header"
    if b"%%EOF" not in blob[-2048:]:
        return False, "missing %%EOF trailer"
    return True, f"ok ({len(blob)} bytes)"


def verify_file(path: Path) -> tuple[bool, str]:
    try:
        blob = store.read_bytes(path)
    except OSError as exc:
        return False, f"unreadable: {exc}"
    return verify_bytes(blob)


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


def _safe_name(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_") or "paper"


def _cache_extract(sha: str, path: Path, pages: list[dict[str, Any]],
                   paper_key: str | None) -> Path:
    """The extract cache claims lint reads; a paper_key alias rides along."""
    dump = {"schema_version": contracts.SCHEMA_VERSION, "sha256": sha, "path": str(path),
            "paper_key": paper_key or "",
            "pages": [{"page_no": p["page_no"], "raw_text": p["raw_text"]} for p in pages],
            "created_at": store.now()}
    out = store.cache_dir() / "extracts" / f"{sha}.json"
    store.write_json_atomic(out, dump)
    if paper_key:
        alias = store.cache_dir() / "extracts" / "by-key" / f"{_safe_name(paper_key)}.json"
        store.write_json_atomic(alias, dump)
    return out


def _render_pages(doc: Any, total: int, count: int, sha: str) -> tuple[list[str], list[str]]:
    rendered: list[str] = []
    errors: list[str] = []
    limit = total if count < 0 else min(total, count)
    dpi = int(str(canon.value("pdf.render_dpi")))
    for n in range(limit):
        try:
            pix = doc.load_page(n).get_pixmap(dpi=dpi)
            png = pix.tobytes("png")
        except Exception as exc:
            errors.append(f"p{n + 1}: {type(exc).__name__}: {exc}")
            continue
        out = store.cache_dir() / "pages" / sha[:12] / f"p{n + 1:03d}.png"
        store.write_bytes_atomic(out, png)
        rendered.append(str(out))
    return rendered, errors


def extract(path_str: str, max_pages: int = 0, run_id: str | None = None,
            render: int = 0, paper_key: str | None = None) -> dict[str, Any]:
    """Extract {text_md, pages[...], fallback}; gate -> parse -> cache -> trace."""
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
        blob = store.read_bytes(path)
    except OSError as exc:
        return _fail(f"pdf unreadable: {exc}", fallback_chain=fallback)
    ok, detail = verify_bytes(blob)
    if not ok:
        return _fail(f"pdf integrity gate: {detail}", fallback_chain=fallback)
    sha = hashlib.sha256(blob).hexdigest()
    try:
        doc = fitz.open(stream=blob, filetype="pdf")
    except Exception as exc:
        return _fail(f"pdf open failed: {type(exc).__name__}: {exc}",
                     fallback_chain=fallback)
    pages: list[dict[str, Any]] = []
    rendered: list[str] = []
    render_errors: list[str] = []
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
        if render:
            rendered, render_errors = _render_pages(doc, total, render, sha)
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
    cache_path = _cache_extract(sha, path, pages, paper_key)
    if run_id:
        run = runs.load(run_id)
        if run is not None and run.status == "active":
            runs.append_trace(run, "PDF_EXTRACT", f"{sha[:12]} {len(pages)}p")
            runs.save(run)
    return {"ok": True, "path": str(path), "sha256": sha, "pages": len(pages),
            "chars": sum(len(p["raw_text"]) for p in pages),
            "needs_ocr_pages": sum(1 for p in pages if p["needs_ocr"]),
            "meta": meta,
            "text_md": text_md, "page_list": pages, "cache_path": str(cache_path),
            "rendered": rendered, "render_errors": render_errors,
            "fallback_chain": ["pymupdf-text"] + fallback, "errors": []}


def _unpaywall_pdf(doi: str, timeout: int) -> tuple[str | None, dict | None]:
    body, err = net._fetch(
        f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}",
        {"email": str(canon.value("search.polite_pool_mailto"))}, timeout)
    if err or body is None:
        return None, err or net._envelope("unpaywall", "network", "no body")
    doc, perr = net._json_body(body, "unpaywall")
    if doc is None:
        return None, perr
    for loc in [doc.get("best_oa_location") or {}, *(doc.get("oa_locations") or [])]:
        url = str((loc or {}).get("url_for_pdf") or "").strip()
        if url:
            return url, None
    return None, None


def _europepmc_pdf(pmid: str, timeout: int) -> tuple[str | None, dict | None]:
    body, err = net._fetch("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        {"query": f"EXT_ID:{pmid}", "format": "json", "resultType": "core"}, timeout)
    if err or body is None:
        return None, err or net._envelope("europepmc", "network", "no body")
    doc, perr = net._json_body(body, "europepmc")
    if doc is None:
        return None, perr
    hits = (doc.get("resultList") or {}).get("result") or []
    for hit in hits:
        pmcid = str(hit.get("pmcid") or "").strip()
        if pmcid:
            return (f"https://www.ebi.ac.uk/europepmc/webservices/rest/"
                    f"{urllib.parse.quote(pmcid)}/fullTextPDF"), None
    return None, None


def fetch(identifiers: dict[str, str], run_id: str | None = None,
          name: str | None = None) -> dict[str, Any]:
    """OA waterfall (canon pdf.fetch_order) into paper_root/_inbox.

    Every candidate passes the completeness gate before it is kept; failures
    delete the partial file and fall through to the next channel."""
    doi = str(identifiers.get("doi") or "").strip()
    arxiv_id = str(identifiers.get("arxiv_id") or "").strip()
    pmid = str(identifiers.get("pmid") or "").strip()
    if not (doi or arxiv_id or pmid):
        return _fail("pdf-fetch needs at least one identifier (doi/arxiv_id/pmid)")
    timeout = int(str(canon.value("search.timeout_seconds")))
    stem = _safe_name(name or doi or arxiv_id or f"pmid-{pmid}")[:80]
    dest = canon.paper_root() / "_inbox" / f"{stem}.pdf"
    if dest.exists():
        return _fail(f"target already exists: {dest}")
    attempts: list[dict[str, Any]] = []
    for source in [str(s) for s in canon.value("pdf.fetch_order")]:
        url: str | None = None
        lookup_err: dict | None = None
        if source == "unpaywall":
            if not doi:
                attempts.append({"source": source, "result": "skipped (no doi)"})
                continue
            url, lookup_err = _unpaywall_pdf(doi, timeout)
        elif source == "arxiv":
            if not arxiv_id:
                attempts.append({"source": source, "result": "skipped (no arxiv_id)"})
                continue
            url = f"https://export.arxiv.org/pdf/{urllib.parse.quote(arxiv_id)}"
        elif source == "europepmc":
            if not pmid:
                attempts.append({"source": source, "result": "skipped (no pmid)"})
                continue
            url, lookup_err = _europepmc_pdf(pmid, timeout)
        else:
            attempts.append({"source": source, "result": "unknown channel"})
            continue
        if lookup_err or not url:
            detail = f"lookup failed: {str(lookup_err.get('message'))[:80]}" if lookup_err else "no oa url"
            attempts.append({"source": source, "result": detail})
            continue
        blob, download_err = net._fetch_bytes(url, {}, timeout)
        if download_err or not blob:
            message = str((download_err or {}).get("message", "empty body"))[:80]
            attempts.append({"source": source, "result": f"download failed: {message}"})
            continue
        store.write_bytes_atomic(dest, blob)
        ok, detail = verify_bytes(blob)
        if not ok:
            store.delete_file(dest)
            attempts.append({"source": source, "result": f"gate rejected: {detail}"})
            continue
        sha = store.sha256_file(dest)
        if run_id:
            run = runs.load(run_id)
            if run is not None and run.status == "active":
                runs.append_trace(run, "PDF_FETCH", f"{sha[:12]} {source}")
                runs.save(run)
        return {"ok": True, "path": str(dest), "bytes": len(blob), "sha256": sha,
                "source": source, "attempts": attempts}
    return _fail("all fetch channels failed", attempts=attempts)
