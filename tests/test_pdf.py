"""L2 pdf: integrity gate, text-layer contract, cache/renders, OA waterfall."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pipelines import canon, pdf

RUN = "WEEKLYRUN-20260921-120000"
GOOD_PDF = b"%PDF-1.4\n" + b"0" * 100_100 + b"\n%%EOF\n"


class _Pix:
    def tobytes(self, fmt):
        return b"\x89PNG\r\n\x1a\n" + fmt.encode()


class _Page:
    def __init__(self, text, images=()):
        self._text = text
        self._images = images
        self.dpi = None

    def get_text(self, _kind):
        return self._text

    def get_images(self):
        return self._images

    def get_pixmap(self, dpi=0):
        self.dpi = dpi
        return _Pix()


class _Doc:
    def __init__(self, pages, meta=None):
        self._pages = pages
        self.page_count = len(pages)
        self.metadata = meta or {}
        self.closed = False

    def load_page(self, n):
        page = self._pages[n]
        if isinstance(page, Exception):
            raise page
        return page

    def close(self):
        self.closed = True


class _Fitz:
    def __init__(self, pages, meta=None):
        self._pages = pages
        self._meta = meta

    def open(self, stream, filetype):
        assert filetype == "pdf" and isinstance(stream, bytes)
        return _Doc(self._pages, self._meta)


def _patch(monkeypatch, pages, meta=None):
    monkeypatch.setattr(pdf, "_import_fitz", lambda: _Fitz(pages, meta))
    monkeypatch.setattr(pdf, "_mineru_available", lambda: False)


def _write_pdf(tmp_path, name="a.pdf"):
    path = tmp_path / name
    path.write_bytes(GOOD_PDF)
    return path


def test_gate_rejects_incomplete_files(monkeypatch, tmp_path):
    _patch(monkeypatch, [_Page("hello")])
    tiny = tmp_path / "tiny.pdf"
    tiny.write_bytes(b"%PDF-1.4 too small")
    out = pdf.extract(str(tiny))
    assert not out["ok"] and "integrity gate" in out["error"] and "too small" in out["error"]
    headless = tmp_path / "headless.pdf"
    headless.write_bytes(b"X" * 100_100 + b"%%EOF")
    assert "missing %PDF header" in pdf.extract(str(headless))["error"]
    eofless = tmp_path / "eofless.pdf"
    eofless.write_bytes(b"%PDF-1.4\n" + b"0" * 100_100)
    assert "missing %%EOF trailer" in pdf.extract(str(eofless))["error"]
    assert pdf.verify_bytes(GOOD_PDF)[0] is True


def test_extract_contract_and_empty_page(monkeypatch, tmp_path):
    src = _write_pdf(tmp_path)
    _patch(monkeypatch, [_Page("hello world"), _Page("   ")])
    out = pdf.extract(str(src))
    assert out["ok"] and out["pages"] == 2 and out["chars"] == len("hello world   ")
    assert out["page_list"][0] == {"page_no": 1, "raw_text": "hello world",
                                   "errors": [], "needs_ocr": False}
    assert out["page_list"][1]["errors"] == ["empty-text"]
    assert out["page_list"][1]["needs_ocr"] is False
    assert out["needs_ocr_pages"] == 0 and out["meta"] == {"title": "", "author": ""}
    assert "--- p2 ---" in out["text_md"]
    assert out["fallback_chain"][0] == "pymupdf-text"


def test_extract_flags_scanned_pages_and_meta(monkeypatch, tmp_path):
    src = _write_pdf(tmp_path, "scan.pdf")
    _patch(monkeypatch, [_Page("   ", images=[("img",)])],
           meta={"title": "Scanned", "author": "AN"})
    out = pdf.extract(str(src))
    assert out["page_list"][0]["needs_ocr"] is True
    assert out["needs_ocr_pages"] == 1
    assert out["meta"] == {"title": "Scanned", "author": "AN"}


def test_extract_page_error_isolation(monkeypatch, tmp_path):
    src = _write_pdf(tmp_path, "b.pdf")
    _patch(monkeypatch, [_Page("kept"), ValueError("broken page")])
    out = pdf.extract(str(src))
    assert out["ok"] and out["page_list"][1]["errors"] == ["ValueError: broken page"]
    assert "kept" in out["text_md"]


def test_extract_envelopes(monkeypatch, tmp_path):
    missing = pdf.extract(str(tmp_path / "nope.pdf"))
    assert not missing["ok"] and "not found" in missing["error"]
    blocked = pdf.extract(str(Path(canon.forbidden_roots()[0]) / "x.pdf"))
    assert not blocked["ok"] and "forbidden" in blocked["error"]
    monkeypatch.setattr(pdf, "_import_fitz", lambda: None)
    src = _write_pdf(tmp_path, "c.pdf")
    nofitz = pdf.extract(str(src))
    assert not nofitz["ok"] and "pymupdf-missing" in nofitz["fallback_chain"]


def test_extract_writes_cache_alias_and_renders(monkeypatch, tmp_path):
    src = _write_pdf(tmp_path)
    _patch(monkeypatch, [_Page("p1 text"), _Page("p2 text")])
    out = pdf.extract(str(src), render=2, paper_key="doi:10.1/x")
    assert out["ok"] and out["sha256"] == hashlib.sha256(GOOD_PDF).hexdigest()
    from pipelines import store

    dump = store.read_json(store.cache_dir() / "extracts" / f"{out['sha256']}.json")
    assert [p["page_no"] for p in dump["pages"]] == [1, 2]
    assert dump["paper_key"] == "doi:10.1/x"
    alias = store.cache_dir() / "extracts" / "by-key" / "doi_10.1_x.json"
    assert alias.is_file()
    assert len(out["rendered"]) == 2
    assert all(Path(p).is_file() for p in out["rendered"])
    assert out["rendered"][0].endswith("p001.png")


def test_fetch_waterfall_and_trace(monkeypatch, tmp_path, frozen_clock):
    from pipelines import runs

    runs.start("weekly", RUN)
    seen = []

    def fake_fetch(url, params, timeout):
        seen.append(url)
        if "unpaywall" in url:
            return '{"best_oa_location": {"url_for_pdf": "https://oa.example/p.pdf"}}', None
        return None, {"source": "x", "category": "http", "message": "404"}

    def fake_bytes(url, params, timeout):
        seen.append(url)
        return GOOD_PDF, None

    monkeypatch.setattr(pdf.net, "_fetch", fake_fetch)
    monkeypatch.setattr(pdf.net, "_fetch_bytes", fake_bytes)
    out = pdf.fetch({"doi": "10.1/x"}, run_id=RUN)
    assert out["ok"] and out["source"] == "unpaywall"
    assert out["bytes"] == len(GOOD_PDF) and any("unpaywall" in u for u in seen)
    dest = Path(out["path"])
    assert dest.is_file() and dest.parent.name == "_inbox"
    assert runs.load(RUN).trace[-1]["event"] == "PDF_FETCH"
    dup = pdf.fetch({"doi": "10.1/x"})
    assert not dup["ok"] and "already exists" in dup["error"]


def test_fetch_gate_rejects_garbage_and_falls_through(monkeypatch, tmp_path):
    def fake_fetch(url, params, timeout):
        return '{"best_oa_location": {"url_for_pdf": "https://oa.example/scan.pdf"}}', None

    def fake_bytes(url, params, timeout):
        if "scan.pdf" in url:
            return b"<html>not a pdf</html>", None
        return GOOD_PDF, None

    monkeypatch.setattr(pdf.net, "_fetch", fake_fetch)
    monkeypatch.setattr(pdf.net, "_fetch_bytes", fake_bytes)
    out = pdf.fetch({"doi": "10.1/y", "arxiv_id": "2501.00001"})
    assert out["ok"] and out["source"] == "arxiv"
    assert "gate rejected" in out["attempts"][0]["result"]
    assert out["attempts"][0]["source"] == "unpaywall"


def test_fetch_needs_identifier(tmp_path):
    out = pdf.fetch({})
    assert not out["ok"] and "needs at least one identifier" in out["error"]
