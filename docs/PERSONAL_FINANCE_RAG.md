# Personal Finance RAG (Phase 10)

## Storage & Architecture
`backend/app/services/assistant/rag_service.py` indexes eligible user-owned Phase 7 documents (`FinancialDocument` + `DocumentExtraction`) into PostgreSQL table `document_rag_chunks` (`DocumentRagChunk`).

- **Strict Tenant Scoping:** Every query filters by `DocumentRagChunk.user_id == user_id` and joins `FinancialDocument` verifying `FinancialDocument.user_id == user_id`. Cross-user document leakage is impossible.
- **Confirmed vs. Unreviewed Provenance:** Chunks carry `is_confirmed_source` (`True` only when `processing_status == "confirmed"`). Retrieved evidence badges clearly distinguish `"Confirmed Document"` from `"OCR Extracted (Unreviewed)"` in the UI and prompt context.
- **Page Traceability:** Multi-page OCR markers (`--- Page N ---`) are parsed into real `page_number` metadata when present; page numbers are never guessed when unavailable.
- **Cleanup & Deduplication:**
  - Chunks deduplicate via per-document SHA-256 `content_hash` (`uq_rag_doc_content_hash`).
  - Deleting or rejecting a document calls `purge_document_chunks` inside `DocumentService` (backed by `ON DELETE CASCADE`), immediately removing chunks from retrieval.
- **Hybrid Retrieval:** Local CPU TF-IDF cosine similarity + keyword token overlap ranks top-K relevant document chunks without sending private documents to any external vector DB or web search service.
