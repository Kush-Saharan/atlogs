"""Document parsing (Docling) — turn any PDF into structured, provenance-tagged
content that the SAME resolution pipeline can consume.

Design goals (per the generalization requirement — nothing here is tuned to a
specific document):
  * Docling parses the PDF into a `DoclingDocument`; we export three views, each
    with {page, section} provenance:
        - `tables`   : structured rows (fed to schema discovery like any source)
        - `chunks`   : narrative passages grouped by section heading
        - `markdown` : the full readable document (kept for the OKF/citation view)
  * The full Docling serialization (`export_to_dict()`) is kept verbatim as the
    DURABLE artifact — the chain-of-custody record saved before any extraction.
  * Heavy + blocking: Docling loads ML models and does layout analysis, so the
    converter is a lazy singleton and callers must run `parse_pdf` off the event
    loop (it already hops to a thread). OCR is OFF by default (digital-native
    PDFs) to avoid the largest model downloads; enable per call if needed.
  * Graceful degradation: importing this module never imports Docling. A parse
    attempt raises a clear error if Docling/models are unavailable, rather than
    crashing the server.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Any

# Docling fetches its layout/table models from the HuggingFace Hub, which tries
# to symlink into the cache. On Windows without Developer Mode/admin that raises
# WinError 1314; disabling symlinks makes HF copy files instead. Must be set
# before huggingface_hub is imported (i.e. before Docling loads its models).
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# Target size for a narrative chunk (characters). Chunks respect section
# boundaries; a long section is split into several ~this-size chunks.
_CHUNK_CHARS = 1400
_CHUNK_OVERLAP = 150

# Above this page count, skip Docling's memory-heavy image/layout pipeline and
# use the low-memory text extractor (avoids std::bad_alloc on constrained
# machines). Tables/layout are lost for these docs; narrative text is retained.
_MAX_DOCLING_PAGES = 40


def _docling_enabled() -> bool:
    """Master switch for Docling. Set DOCLING_ENABLED=false on small/constrained
    hosts (e.g. a 512 MB free tier) where torch/Docling would OOM — every PDF
    then uses the low-memory text-only extractor. Tables/layout are lost; the
    narrative text (what IE reads) is retained, so PDF ingestion still works."""
    return os.getenv("DOCLING_ENABLED", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )

_converter: Any = None  # lazy Docling DocumentConverter singleton


@dataclass
class DocTable:
    page: int | None
    section: str
    columns: list[str]
    rows: list[dict[str, Any]]


@dataclass
class DocChunk:
    index: int
    text: str
    page: int | None
    section: str  # heading path, e.g. "Findings > Root cause"


@dataclass
class ParsedDocument:
    filename: str
    sha256: str
    parser: str  # "docling" | "docling-no-tables" | ...
    page_count: int
    title: str
    markdown: str
    sections: list[str]  # heading outline
    tables: list[DocTable] = field(default_factory=list)
    chunks: list[DocChunk] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)  # durable Docling export

    def stats(self) -> dict[str, int]:
        return {
            "pages": self.page_count,
            "sections": len(self.sections),
            "tables": len(self.tables),
            "chunks": len(self.chunks),
            "markdown_chars": len(self.markdown),
        }


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _get_converter(ocr: bool) -> Any:
    """Build (once) a Docling converter. OCR off by default; TableFormer FAST."""
    global _converter
    if _converter is not None:
        return _converter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        TableFormerMode,
    )
    from docling.datamodel.settings import settings as docling_settings
    from docling.document_converter import DocumentConverter, PdfFormatOption

    # Process ONE page at a time so memory is released between them — large
    # reports (100+ pages) otherwise rasterize many pages at once and OOM
    # (std::bad_alloc) on constrained machines. If Docling still fails to render
    # (very large pages), parse_pdf_bytes falls back to a low-memory text parse.
    try:
        docling_settings.perf.page_batch_size = 1
    except Exception:
        pass

    opts = PdfPipelineOptions()
    opts.do_ocr = ocr
    opts.do_table_structure = True
    # We never need rendered page/figure images — skip them to save memory.
    for attr in ("generate_page_images", "generate_picture_images"):
        try:
            setattr(opts, attr, False)
        except Exception:
            pass
    try:
        opts.images_scale = 1.0
    except Exception:
        pass
    try:
        opts.table_structure_options.mode = TableFormerMode.FAST
    except Exception:
        pass
    _converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )
    return _converter


def _page_of(item: Any) -> int | None:
    prov = getattr(item, "prov", None) or []
    if prov:
        p = getattr(prov[0], "page_no", None)
        if isinstance(p, int):
            return p
    return None


def _extract_tables(doc: Any) -> list[DocTable]:
    tables: list[DocTable] = []
    for t in getattr(doc, "tables", []) or []:
        cols: list[str] = []
        rows: list[dict[str, Any]] = []
        try:
            df = t.export_to_dataframe()
            cols = [str(c) for c in df.columns]
            for rec in df.to_dict(orient="records"):
                rows.append({str(k): ("" if v is None else str(v)) for k, v in rec.items()})
        except Exception:
            continue
        if rows:
            tables.append(DocTable(page=_page_of(t), section="", columns=cols, rows=rows))
    return tables


def _extract_chunks_and_outline(doc: Any) -> tuple[list[DocChunk], list[str]]:
    """Walk text items in reading order, grouping under the current heading path.

    Uses only stable attributes (text/label/prov) so it tolerates Docling
    version drift. Falls back to markdown-header splitting if `texts` is absent.
    """
    outline: list[str] = []
    chunks: list[DocChunk] = []
    heading_stack: list[str] = []
    buf: list[str] = []
    buf_page: int | None = None
    idx = 0

    def section_path() -> str:
        return " > ".join(heading_stack[-3:])

    def flush() -> None:
        nonlocal buf, buf_page, idx
        text = " ".join(s.strip() for s in buf if s.strip()).strip()
        buf = []
        if not text:
            buf_page = None
            return
        # split oversized sections into overlapping ~_CHUNK_CHARS windows
        start = 0
        while start < len(text):
            piece = text[start : start + _CHUNK_CHARS]
            chunks.append(
                DocChunk(index=idx, text=piece.strip(), page=buf_page, section=section_path())
            )
            idx += 1
            if start + _CHUNK_CHARS >= len(text):
                break
            start += _CHUNK_CHARS - _CHUNK_OVERLAP
        buf_page = None

    texts = getattr(doc, "texts", None)
    if texts:
        for item in texts:
            label = str(getattr(item, "label", "") or "").lower()
            text = str(getattr(item, "text", "") or "").strip()
            if not text:
                continue
            is_heading = "header" in label or label in ("title", "section_header")
            if is_heading:
                flush()
                # maintain a shallow heading stack (title resets)
                if label == "title":
                    heading_stack[:] = [text]
                else:
                    if heading_stack:
                        heading_stack[-1] = text
                    else:
                        heading_stack.append(text)
                if text not in outline:
                    outline.append(text)
            else:
                if buf_page is None:
                    buf_page = _page_of(item)
                buf.append(text)
        flush()

    return chunks, outline


def _chunks_from_markdown(md: str) -> tuple[list[DocChunk], list[str]]:
    """Fallback chunker: split markdown on headings, then size-window."""
    outline: list[str] = []
    chunks: list[DocChunk] = []
    idx = 0
    current = ""
    section_buf: list[str] = []

    def flush() -> None:
        nonlocal section_buf, idx
        text = "\n".join(section_buf).strip()
        section_buf = []
        if not text:
            return
        start = 0
        while start < len(text):
            piece = text[start : start + _CHUNK_CHARS]
            chunks.append(DocChunk(index=idx, text=piece.strip(), page=None, section=current))
            idx += 1
            if start + _CHUNK_CHARS >= len(text):
                break
            start += _CHUNK_CHARS - _CHUNK_OVERLAP

    for line in md.splitlines():
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if m:
            flush()
            current = m.group(1).strip()
            if current and current not in outline:
                outline.append(current)
        else:
            section_buf.append(line)
    flush()
    return chunks, outline


def _parse_pdf_textonly(data: bytes, filename: str) -> ParsedDocument:
    """Low-memory fallback: extract text per page with pypdfium2 (NO rasterization,
    NO layout model), so large PDFs that OOM Docling's image pipeline still yield
    usable narrative text. Loses tables/section structure — labeled accordingly."""
    import pypdfium2 as pdfium

    digest = sha256_of(data)
    chunks: list[DocChunk] = []
    md_parts: list[str] = []
    page_count = 0
    idx = 0
    pdf = pdfium.PdfDocument(data)
    try:
        page_count = len(pdf)
        for pno in range(page_count):
            page = pdf[pno]
            try:
                tp = page.get_textpage()
                text = (tp.get_text_range() or "").strip()
                tp.close()
            except Exception:
                text = ""
            finally:
                page.close()
            if not text:
                continue
            md_parts.append(text)
            start = 0
            while start < len(text):
                piece = text[start : start + _CHUNK_CHARS]
                chunks.append(
                    DocChunk(index=idx, text=piece.strip(), page=pno + 1, section="")
                )
                idx += 1
                if start + _CHUNK_CHARS >= len(text):
                    break
                start += _CHUNK_CHARS - _CHUNK_OVERLAP
    finally:
        pdf.close()

    return ParsedDocument(
        filename=filename,
        sha256=digest,
        parser="pypdfium2-text",
        page_count=page_count,
        title=filename or "document",
        markdown="\n\n".join(md_parts),
        sections=[],
        tables=[],
        chunks=chunks,
        raw={"parser": "pypdfium2-text", "pages": page_count},
    )


def parse_pdf_bytes(data: bytes, filename: str, *, ocr: bool = False) -> ParsedDocument:
    """Parse a PDF (bytes) into a structured, provenance-tagged ParsedDocument.

    Blocking + heavy (loads models). Call via `parse_pdf` to run off-thread. If
    Docling raises or returns almost no content (e.g. rasterization OOM on a huge
    report), fall back to a low-memory text-only parse so the document is never
    lost or ingested empty.
    """
    import tempfile
    from pathlib import Path

    digest = sha256_of(data)

    # Master switch: on constrained hosts Docling/torch is disabled entirely and
    # every PDF goes through the low-memory text-only extractor.
    if not _docling_enabled():
        return _parse_pdf_textonly(data, filename)

    # Large PDFs OOM Docling's page-rasterization pipeline — and a native
    # std::bad_alloc can hard-crash the process (it's not a catchable Python
    # exception). So for big documents we skip the image pipeline entirely and
    # use the low-memory text extractor, which still yields narrative text for IE
    # (losing only table structure). Page count is read cheaply (no rendering).
    try:
        import pypdfium2 as pdfium

        _pdf = pdfium.PdfDocument(data)
        _pages = len(_pdf)
        _pdf.close()
        if _pages > _MAX_DOCLING_PAGES:
            return _parse_pdf_textonly(data, filename)
    except Exception:
        pass

    try:
        converter = _get_converter(ocr)
        # Docling wants a path/stream; a temp file is the most version-robust input.
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / (filename or "document.pdf")
            p.write_bytes(data)
            result = converter.convert(str(p))
        doc = result.document
        try:
            markdown = doc.export_to_markdown()
        except Exception:
            markdown = ""
        try:
            raw = doc.export_to_dict()
        except Exception:
            raw = {}
        page_count = 0
        try:
            page_count = len(getattr(doc, "pages", {}) or {})
        except Exception:
            pass
        title = str(getattr(doc, "name", "") or filename or "document")
        tables = _extract_tables(doc)
        chunks, outline = _extract_chunks_and_outline(doc)
        parser = "docling"
        if not chunks:  # text-item walk yielded nothing → try markdown split
            chunks, outline = _chunks_from_markdown(markdown)
            parser = "docling-md"

        # If Docling produced almost nothing on a multi-page doc (rasterization
        # failures / std::bad_alloc leave empty pages), recover the text cheaply.
        degraded = (len(chunks) == 0 or len(markdown.strip()) < 400) and page_count > 2
        if degraded:
            fb = _parse_pdf_textonly(data, filename)
            if fb.chunks:
                return fb

        return ParsedDocument(
            filename=filename,
            sha256=digest,
            parser=parser,
            page_count=page_count,
            title=title,
            markdown=markdown,
            sections=outline,
            tables=tables,
            chunks=chunks,
            raw=raw,
        )
    except Exception:
        # Docling failed outright (OOM, bad model, corrupt render) — never lose
        # the document; extract what text we can with near-zero memory.
        return _parse_pdf_textonly(data, filename)


async def parse_pdf(data: bytes, filename: str, *, ocr: bool = False) -> ParsedDocument:
    """Async wrapper — runs the blocking Docling parse in a worker thread."""
    return await asyncio.to_thread(parse_pdf_bytes, data, filename, ocr=ocr)


# --- (de)serialization for durable storage ---------------------------------
def parsed_to_dict(doc: ParsedDocument) -> dict[str, Any]:
    """Serialize a ParsedDocument to a JSON-safe dict (durable custody record)."""
    return {
        "filename": doc.filename,
        "sha256": doc.sha256,
        "parser": doc.parser,
        "page_count": doc.page_count,
        "title": doc.title,
        "markdown": doc.markdown,
        "sections": list(doc.sections),
        "tables": [
            {"page": t.page, "section": t.section, "columns": t.columns, "rows": t.rows}
            for t in doc.tables
        ],
        "chunks": [
            {"index": c.index, "text": c.text, "page": c.page, "section": c.section}
            for c in doc.chunks
        ],
        "raw": doc.raw,
    }


def parsed_from_dict(d: dict[str, Any]) -> ParsedDocument:
    """Reconstruct a ParsedDocument from its stored dict (recovery / reprocess)."""
    return ParsedDocument(
        filename=d.get("filename", ""),
        sha256=d.get("sha256", ""),
        parser=d.get("parser", ""),
        page_count=int(d.get("page_count", 0) or 0),
        title=d.get("title", ""),
        markdown=d.get("markdown", ""),
        sections=list(d.get("sections", []) or []),
        tables=[
            DocTable(
                page=t.get("page"),
                section=t.get("section", ""),
                columns=list(t.get("columns", []) or []),
                rows=list(t.get("rows", []) or []),
            )
            for t in (d.get("tables") or [])
        ],
        chunks=[
            DocChunk(
                index=int(c.get("index", i)),
                text=c.get("text", ""),
                page=c.get("page"),
                section=c.get("section", ""),
            )
            for i, c in enumerate(d.get("chunks") or [])
        ],
        raw=d.get("raw") or {},
    )
