"""L2 pdf: text-layer contract, per-page errors, probe degradation, envelopes."""

from __future__ import annotations

from pipelines import pdf


class _Page:
    def __init__(self, text, images=()):
        self._text = text
        self._images = images

    def get_text(self, _kind):
        return self._text

    def get_images(self):
        return self._images


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


def test_extract_contract_and_empty_page(monkeypatch, tmp_path):
    src = tmp_path / "a.pdf"
    src.write_bytes(b"%PDF-1.4")
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
    src = tmp_path / "scan.pdf"
    src.write_bytes(b"%PDF-1.4")
    _patch(monkeypatch, [_Page("   ", images=[("img",)])],
           meta={"title": "Scanned", "author": "AN"})
    out = pdf.extract(str(src))
    assert out["page_list"][0]["needs_ocr"] is True
    assert out["needs_ocr_pages"] == 1
    assert out["meta"] == {"title": "Scanned", "author": "AN"}


def test_extract_page_error_isolation(monkeypatch, tmp_path):
    src = tmp_path / "b.pdf"
    src.write_bytes(b"%PDF-1.4")
    _patch(monkeypatch, [_Page("kept"), ValueError("broken page")])
    out = pdf.extract(str(src))
    assert out["ok"] and out["page_list"][1]["errors"] == ["ValueError: broken page"]
    assert "kept" in out["text_md"]


def test_extract_envelopes(monkeypatch, tmp_path):
    missing = pdf.extract(str(tmp_path / "nope.pdf"))
    assert not missing["ok"] and "not found" in missing["error"]
    blocked = pdf.extract("E:\\Project\\x.pdf")
    assert not blocked["ok"] and "forbidden" in blocked["error"]
    monkeypatch.setattr(pdf, "_import_fitz", lambda: None)
    src = tmp_path / "c.pdf"
    src.write_bytes(b"%PDF-1.4")
    nofitz = pdf.extract(str(src))
    assert not nofitz["ok"] and "pymupdf-missing" in nofitz["fallback_chain"]
