import hashlib
import re
import uuid

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.assistant import DocumentRagChunk
from app.models.documents import FinancialDocument
from app.schemas.assistant import EvidenceItem
from app.services.web_research.source_validation import sanitize_untrusted_text

_PAGE_SPLIT = re.compile(r"---\s*Page\s*(\d+)\s*---", re.I)


def _chunk_text(text: str, *, chunk_size: int = 850, overlap: int = 120) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunks.append(cleaned[start:end].strip())
        if end >= len(cleaned):
            break
        start = max(start + 1, end - overlap)
    return chunks


def purge_document_chunks(db: Session, user_id: uuid.UUID, document_id: uuid.UUID) -> int:
    res = db.execute(
        delete(DocumentRagChunk).where(
            DocumentRagChunk.user_id == user_id,
            DocumentRagChunk.document_id == document_id,
        )
    )
    return int(res.rowcount or 0)


def reindex_user_documents(db: Session, user_id: uuid.UUID) -> tuple[int, int, int]:
    """
    Synchronize PostgreSQL RAG chunks with user's active non-rejected Phase 7 documents
    and OCR extractions without re-running OCR or crossing tenant boundaries.
    """
    docs = list(
        db.execute(
            select(FinancialDocument)
            .options(selectinload(FinancialDocument.extraction))
            .where(FinancialDocument.user_id == user_id)
        )
        .scalars()
        .all()
    )

    docs_scanned = 0
    chunks_indexed = 0
    chunks_removed = 0

    for doc in docs:
        docs_scanned += 1
        if doc.processing_status == "rejected":
            chunks_removed += purge_document_chunks(db, user_id, doc.id)
            continue

        ext = doc.extraction
        if ext is None:
            continue

        is_confirmed = doc.processing_status == "confirmed"
        parts: list[tuple[int | None, str]] = []

        # Structured summary chunk (accurate metadata)
        meta_lines = [f"Document: {doc.original_filename} ({doc.document_category})"]
        meta_lines.append(
            f"Verification status: {'Confirmed by user' if is_confirmed else 'OCR extracted (needs review)'}"
        )
        if ext.merchant_name:
            meta_lines.append(f"Merchant: {ext.merchant_name}")
        if ext.invoice_number:
            meta_lines.append(f"Invoice Number: {ext.invoice_number}")
        if ext.invoice_date:
            meta_lines.append(f"Invoice Date: {ext.invoice_date.isoformat()}")
        if ext.due_date:
            meta_lines.append(f"Due Date: {ext.due_date.isoformat()}")
        if ext.grand_total is not None:
            meta_lines.append(f"Grand Total: {ext.currency or 'INR'} {ext.grand_total}")
        if ext.gstin:
            meta_lines.append(f"GSTIN: {ext.gstin}")
        parts.append((1 if doc.page_count == 1 else None, " | ".join(meta_lines)))

        raw = (ext.raw_text or "").strip()
        if raw:
            page_matches = list(_PAGE_SPLIT.finditer(raw))
            if page_matches:
                for i, m in enumerate(page_matches):
                    page_num = int(m.group(1))
                    seg_start = m.end()
                    seg_end = page_matches[i + 1].start() if i + 1 < len(page_matches) else len(raw)
                    for ch in _chunk_text(raw[seg_start:seg_end]):
                        parts.append((page_num, ch))
            else:
                default_page = 1 if doc.page_count == 1 else None
                for ch in _chunk_text(raw):
                    parts.append((default_page, ch))

        existing_chunks = {
            c.chunk_index: c
            for c in db.execute(
                select(DocumentRagChunk).where(
                    DocumentRagChunk.user_id == user_id,
                    DocumentRagChunk.document_id == doc.id,
                )
            )
            .scalars()
            .all()
        }

        desired_indices: set[int] = set()
        for idx, (page_num, content_txt) in enumerate(parts):
            safe_content = sanitize_untrusted_text(content_txt, max_chars=1200)
            if not safe_content:
                continue
            desired_indices.add(idx)
            c_hash = hashlib.sha256(safe_content.encode("utf-8")).hexdigest()
            existing = existing_chunks.get(idx)
            if (
                existing is not None
                and existing.content_hash == c_hash
                and existing.is_confirmed_source == is_confirmed
            ):
                continue
            rec = existing or DocumentRagChunk(
                user_id=user_id,
                document_id=doc.id,
                chunk_index=idx,
            )
            rec.source_type = "reviewed_document" if is_confirmed else "document_extraction"
            rec.source_title = doc.original_filename
            rec.page_number = page_num
            rec.content = safe_content
            rec.content_hash = c_hash
            rec.is_confirmed_source = is_confirmed
            rec.meta = {"document_category": doc.document_category}
            db.add(rec)
            chunks_indexed += 1

        # Remove leftover tail chunks if document shrank
        for old_idx, old_rec in existing_chunks.items():
            if old_idx not in desired_indices:
                db.delete(old_rec)
                chunks_removed += 1

    db.commit()
    return docs_scanned, chunks_indexed, chunks_removed


def retrieve_personal_documents(
    db: Session,
    user_id: uuid.UUID,
    query: str,
    *,
    top_k: int = 4,
) -> tuple[list[dict], list[EvidenceItem]]:
    """
    Strictly tenant-scoped retrieval over active (non-rejected) user document chunks.
    Uses hybrid TF-IDF + keyword token overlap locally without external embedding calls.
    """
    # Ensure index reflects current non-rejected documents safely
    reindex_user_documents(db, user_id)

    stmt = (
        select(DocumentRagChunk)
        .join(FinancialDocument, DocumentRagChunk.document_id == FinancialDocument.id)
        .where(
            DocumentRagChunk.user_id == user_id,
            FinancialDocument.user_id == user_id,
            FinancialDocument.processing_status != "rejected",
        )
    )
    chunks = list(db.execute(stmt).scalars().all())
    if not chunks:
        return [], []

    docs_texts = [f"{c.source_title} {c.content}" for c in chunks]
    try:
        vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        mat = vec.fit_transform(docs_texts + [query])
        sims = cosine_similarity(mat[-1:], mat[:-1])[0]
    except Exception:
        sims = [0.0] * len(chunks)

    q_tokens = {tok for tok in re.findall(r"[a-z0-9]{2,}", (query or "").lower())}
    scored: list[tuple[float, DocumentRagChunk]] = []
    for sim, chunk in zip(sims, chunks):
        c_tokens = set(re.findall(r"[a-z0-9]{2,}", f"{chunk.source_title} {chunk.content}".lower()))
        overlap = len(q_tokens & c_tokens) / max(1, len(q_tokens))
        boost = 0.05 if chunk.is_confirmed_source else 0.0
        total_score = float(sim) + (0.35 * overlap) + boost
        if total_score > 0.04:
            scored.append((total_score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [chunk for _, chunk in scored[:top_k]]

    results: list[dict] = []
    evidence: list[EvidenceItem] = []
    for idx, c in enumerate(selected, start=1):
        page_label = f" (Page {c.page_number})" if c.page_number is not None else ""
        results.append(
            {
                "document_id": str(c.document_id),
                "document_title": c.source_title,
                "page_number": c.page_number,
                "is_confirmed": c.is_confirmed_source,
                "excerpt": c.content,
            }
        )
        evidence.append(
            EvidenceItem(
                evidence_id=f"doc_{idx}",
                origin="personal_document",
                title=f"{c.source_title}{page_label}",
                summary=(
                    f"{'Confirmed document' if c.is_confirmed_source else 'Unreviewed OCR excerpt'}: "
                    f"{c.content[:180]}"
                ),
                source_reference=f"document:{c.document_id}",
                excerpt=c.content,
                content_available=True,
                is_confirmed_source=c.is_confirmed_source,
                meta={"page_number": c.page_number, "chunk_index": c.chunk_index},
            )
        )

    return results, evidence
